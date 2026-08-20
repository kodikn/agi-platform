from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .competitive import COMPETITIVE_STRENGTHS, capability_names


class WorkflowStateStore:
    """Durable JSON-backed workflow checkpoint store for local/runtime recovery."""

    def __init__(self, path: str | Path | None = None) -> None:
        default_path = Path(tempfile.gettempdir()) / "agi-platform" / "workflow-state.json"
        self.path = Path(path or os.getenv("AGI_WORKFLOW_STATE_PATH", default_path))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, workflow: dict[str, Any]) -> None:
        workflows = self.list()
        workflows = [item for item in workflows if item.get("checkpoint") != workflow.get("checkpoint")]
        workflows.append(workflow)
        self._write(workflows)

    def get(self, checkpoint: str, tenant_id: str | None = None) -> dict[str, Any]:
        for workflow in self.list():
            if workflow.get("checkpoint") == checkpoint and (tenant_id is None or workflow.get("tenant_id") == tenant_id):
                return workflow
        raise KeyError(f"checkpoint {checkpoint} not found")

    def update(self, workflow: dict[str, Any]) -> None:
        self.append(workflow)

    def list(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        content = self.path.read_text(encoding="utf-8").strip()
        if not content:
            return []
        data = json.loads(content)
        return data if isinstance(data, list) else []

    def _write(self, workflows: list[dict[str, Any]]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(workflows, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)


@dataclass
class WorkflowEngine:
    state_store: WorkflowStateStore = field(default_factory=WorkflowStateStore)
    runs: list[dict[str, Any]] = field(default_factory=list)

    def plan(self, task: str, agents: list[str] | None = None, tenant_id: str = "default", idempotency_key: str | None = None) -> dict[str, Any]:
        agents = agents or ["architect", "implementer", "reviewer"]
        if idempotency_key:
            for existing in self.state_store.list():
                if existing.get("tenant_id") == tenant_id and existing.get("idempotency_key") == idempotency_key:
                    return existing
        checkpoint = f"{tenant_id}-checkpoint-{len(self.state_store.list()) + 1}"
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
            }
            for index, agent in enumerate(agents)
        ]
        workflow = {
            "tenant_id": tenant_id,
            "idempotency_key": idempotency_key,
            "task": task,
            "steps": steps,
            "checkpoint": checkpoint,
            "status": "planned",
            "created_at": now,
            "updated_at": now,
            "events": [{"type": "workflow.planned", "checkpoint": checkpoint, "timestamp": now}],
            "graph": self._workflow_graph(checkpoint, steps),
            "conversation": self._handoff_trace(steps),
            "crew": {"name": "production-delivery-crew", "agents": agents, "flow": "plan -> execute -> review -> govern"},
            "zero_code_contract": {"task": task, "agents": agents, "approval_required": True},
            "competitive_capabilities": capability_names(),
        }
        self.runs.append(workflow)
        self.state_store.append(workflow)
        return workflow

    def execute(self, checkpoint: str, tenant_id: str = "default") -> dict[str, Any]:
        workflow = self.state_store.get(checkpoint, tenant_id)
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
        workflow["events"].append({"type": "workflow.completed", "checkpoint": checkpoint, "timestamp": workflow["updated_at"]})
        self.state_store.update(workflow)
        return workflow

    def _execute_step(self, task: str, step: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "step.completed",
            "step_id": step["id"],
            "agent": step["agent"],
            "timestamp": int(time.time()),
            "observation": f"{step['agent']} completed governed work on: {task}",
        }

    def _role_for(self, agent: str) -> str:
        roles = {
            "architect": "designs the workflow and constraints",
            "implementer": "executes the approved implementation steps",
            "reviewer": "validates quality, safety, and production readiness",
        }
        return roles.get(agent, "specialized execution agent")

    def _workflow_graph(self, checkpoint: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
        nodes = [step["agent"] for step in steps]
        edges = [{"from": source, "to": target} for source, target in zip(nodes, nodes[1:])]
        return {"checkpoint": checkpoint, "nodes": nodes, "edges": edges, "recovery_enabled": True, "state_store": str(self.state_store.path)}

    def _handoff_trace(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"from": steps[index - 1]["agent"] if index else "user", "to": step["agent"], "message": step["action"]}
            for index, step in enumerate(steps)
        ]

    def competitive_blueprint(self) -> list[dict[str, Any]]:
        return [strength.__dict__ for strength in COMPETITIVE_STRENGTHS]

    def recover(self, checkpoint: str, tenant_id: str = "default") -> dict[str, Any]:
        workflow = self.state_store.get(checkpoint, tenant_id)
        recovered = {**workflow, "status": "recovered", "updated_at": int(time.time())}
        self.state_store.update(recovered)
        return recovered
