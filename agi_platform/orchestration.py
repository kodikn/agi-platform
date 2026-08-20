from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from .competitive import COMPETITIVE_STRENGTHS, capability_names
from .database import (
    Database,
    WorkflowCheckpointRow,
    WorkflowEventRow,
    WorkflowRow,
    WorkflowTaskRow,
    new_id,
    now_ts,
)


class WorkflowStateStore:
    """PostgreSQL-compatible durable workflow state store with SQLite test support."""

    def __init__(
        self, database: Database | None = None, tenant_id: str = "legacy"
    ) -> None:
        self.database = database or Database()
        self.tenant_id = tenant_id
        self.database.create_all()
        self.database.ensure_tenant(tenant_id)
        self.path = "postgresql-compatible"

    def append(self, workflow: dict[str, Any]) -> None:
        self.upsert_workflow(workflow)

    def upsert_workflow(self, workflow: dict[str, Any]) -> None:
        checkpoint = workflow["checkpoint"]
        with self.database.session() as session:
            row = session.get(WorkflowRow, checkpoint)
            if row is None:
                row = WorkflowRow(
                    id=checkpoint,
                    tenant_id=self.tenant_id,
                    task=workflow["task"],
                    status=self._status(workflow.get("status", "planned")),
                    idempotency_key=checkpoint,
                )
                session.add(row)
                session.flush()
            else:
                row.status = self._status(workflow.get("status", row.status))
                row.updated_at = now_ts()
                row.version += 1
                session.flush()
            session.query(WorkflowTaskRow).filter_by(
                workflow_id=checkpoint, tenant_id=self.tenant_id
            ).delete()
            for step in workflow.get("steps", []):
                session.add(
                    WorkflowTaskRow(
                        id=f"{checkpoint}:{step['id']}",
                        tenant_id=self.tenant_id,
                        workflow_id=checkpoint,
                        agent=step["agent"],
                        action=step["action"],
                        status=self._status(step.get("status", "queued")),
                        idempotency_key=f"{checkpoint}:{step['id']}",
                    )
                )
            sequence = (
                session.execute(
                    select(WorkflowEventRow.sequence)
                    .where(
                        WorkflowEventRow.tenant_id == self.tenant_id,
                        WorkflowEventRow.workflow_id == checkpoint,
                    )
                    .order_by(WorkflowEventRow.sequence.desc())
                ).scalar()
                or 0
            ) + 1
            session.merge(
                WorkflowCheckpointRow(
                    id=checkpoint,
                    tenant_id=self.tenant_id,
                    workflow_id=checkpoint,
                    state=workflow,
                    version=row.version,
                )
            )
            session.flush()
            session.add(
                WorkflowEventRow(
                    id=new_id("wfe"),
                    tenant_id=self.tenant_id,
                    workflow_id=checkpoint,
                    event_type="workflow.persisted",
                    sequence=sequence,
                    payload={"status": workflow.get("status")},
                )
            )

    def get(self, checkpoint: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(WorkflowCheckpointRow, checkpoint)
            if row is None or row.tenant_id != self.tenant_id:
                raise KeyError(f"checkpoint {checkpoint} not found")
            return dict(row.state)

    def update(self, workflow: dict[str, Any]) -> None:
        self.upsert_workflow(workflow)

    def list(self) -> list[dict[str, Any]]:
        with self.database.session() as session:
            rows = (
                session.execute(
                    select(WorkflowCheckpointRow).where(
                        WorkflowCheckpointRow.tenant_id == self.tenant_id
                    )
                )
                .scalars()
                .all()
            )
            return [dict(row.state) for row in rows]

    def lease_next_task(
        self, workflow_id: str, worker_id: str, lease_seconds: int = 30
    ) -> str | None:
        now = now_ts()
        with self.database.session() as session:
            task = (
                session.execute(
                    select(WorkflowTaskRow)
                    .where(
                        WorkflowTaskRow.tenant_id == self.tenant_id,
                        WorkflowTaskRow.workflow_id == workflow_id,
                        WorkflowTaskRow.status.in_(["PENDING", "TIMED_OUT"]),
                    )
                    .order_by(WorkflowTaskRow.created_at)
                )
                .scalars()
                .first()
            )
            if task is None:
                return None
            task.status = "RUNNING"
            task.lease_owner = worker_id
            task.lease_expires_at = now + lease_seconds
            task.attempts += 1
            task.updated_at = now
            return task.id

    def mark_task_succeeded(self, task_id: str, worker_id: str) -> bool:
        with self.database.session() as session:
            task = session.get(WorkflowTaskRow, task_id)
            if (
                task is None
                or task.tenant_id != self.tenant_id
                or task.lease_owner != worker_id
                or task.status == "SUCCEEDED"
            ):
                return False
            task.status = "SUCCEEDED"
            task.updated_at = now_ts()
            return True

    def recover_expired_leases(self) -> int:
        now = now_ts()
        recovered = 0
        with self.database.session() as session:
            tasks = (
                session.execute(
                    select(WorkflowTaskRow).where(
                        WorkflowTaskRow.tenant_id == self.tenant_id,
                        WorkflowTaskRow.status == "RUNNING",
                        WorkflowTaskRow.lease_expires_at < now,
                    )
                )
                .scalars()
                .all()
            )
            for task in tasks:
                task.status = (
                    "TIMED_OUT" if task.attempts >= task.max_attempts else "PENDING"
                )
                task.lease_owner = None
                task.lease_expires_at = None
                recovered += 1
        return recovered

    def _status(self, value: str) -> str:
        return {
            "planned": "PENDING",
            "queued": "PENDING",
            "running": "RUNNING",
            "completed": "SUCCEEDED",
            "recovered": "RECOVERING",
        }.get(value, value.upper())


@dataclass
class WorkflowEngine:
    state_store: WorkflowStateStore = field(default_factory=WorkflowStateStore)
    runs: list[dict[str, Any]] = field(default_factory=list)

    def plan(self, task: str, agents: list[str] | None = None) -> dict[str, Any]:
        agents = agents or ["architect", "implementer", "reviewer"]
        checkpoint = f"checkpoint-{len(self.state_store.list()) + 1}"
        now = int(time.time())
        steps = [
            {
                "id": f"step-{index + 1}",
                "agent": agent,
                "role": self._role_for(agent),
                "action": f"{agent} handles {task}",
                "status": "queued",
                "observations": [],
                "retries": 0,
                "idempotency_key": f"{checkpoint}:step-{index + 1}",
            }
            for index, agent in enumerate(agents)
        ]
        workflow = {
            "task": task,
            "steps": steps,
            "checkpoint": checkpoint,
            "status": "planned",
            "created_at": now,
            "updated_at": now,
            "events": [
                {"type": "workflow.planned", "checkpoint": checkpoint, "timestamp": now}
            ],
            "graph": self._workflow_graph(checkpoint, steps),
            "conversation": self._handoff_trace(steps),
            "crew": {
                "name": "production-delivery-crew",
                "agents": agents,
                "flow": "plan -> execute -> review -> govern",
            },
            "zero_code_contract": {
                "task": task,
                "agents": agents,
                "approval_required": True,
            },
            "competitive_capabilities": capability_names(),
        }
        self.runs.append(workflow)
        self.state_store.append(workflow)
        return workflow

    def execute(self, checkpoint: str) -> dict[str, Any]:
        workflow = self.state_store.get(checkpoint)
        if workflow["status"] not in {"planned", "recovered", "running"}:
            return workflow
        workflow["status"] = "running"
        for step in workflow["steps"]:
            if step["status"] == "completed":
                continue
            step["status"] = "running"
            observation = self._execute_step(workflow["task"], step)
            step["observations"].append(observation)
            step["status"] = "completed"
            workflow["events"].append(observation)
        workflow["status"] = "completed"
        workflow["updated_at"] = int(time.time())
        workflow["events"].append(
            {
                "type": "workflow.completed",
                "checkpoint": checkpoint,
                "timestamp": workflow["updated_at"],
            }
        )
        self.state_store.update(workflow)
        return workflow

    def _execute_step(self, task: str, step: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "step.completed",
            "step_id": step["id"],
            "agent": step["agent"],
            "timestamp": int(time.time()),
            "observation": f"{step['agent']} completed governed work on: {task}",
            "idempotency_key": step.get("idempotency_key"),
        }

    def _role_for(self, agent: str) -> str:
        return {
            "architect": "designs the workflow and constraints",
            "implementer": "executes the approved implementation steps",
            "reviewer": "validates quality, safety, and production readiness",
        }.get(agent, "specialized execution agent")

    def _workflow_graph(
        self, checkpoint: str, steps: list[dict[str, Any]]
    ) -> dict[str, Any]:
        nodes = [step["agent"] for step in steps]
        edges = [
            {"from": source, "to": target} for source, target in zip(nodes, nodes[1:])
        ]
        return {
            "checkpoint": checkpoint,
            "nodes": nodes,
            "edges": edges,
            "recovery_enabled": True,
            "state_store": str(self.state_store.path),
        }

    def _handoff_trace(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "from": steps[index - 1]["agent"] if index else "user",
                "to": step["agent"],
                "message": step["action"],
            }
            for index, step in enumerate(steps)
        ]

    def competitive_blueprint(self) -> list[dict[str, Any]]:
        return [strength.__dict__ for strength in COMPETITIVE_STRENGTHS]

    def recover(self, checkpoint: str) -> dict[str, Any]:
        workflow = self.state_store.get(checkpoint)
        recovered = {**workflow, "status": "recovered", "updated_at": int(time.time())}
        self.state_store.update(recovered)
        return recovered
