from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .agent_events import EventLog, MessageEvent


@dataclass
class WorkflowCheckpoint:
    checkpoint_id: str
    task: str
    state: dict[str, Any]
    status: Literal["planned", "paused", "running", "completed", "recovered"]
    event_log: EventLog = field(default_factory=EventLog)

    def to_dict(self) -> dict[str, Any]:
        return {"checkpoint": self.checkpoint_id, "task": self.task, "state": self.state, "status": self.status, "events": self.event_log.all()}


@dataclass
class WorkflowEngine:
    checkpoints: dict[str, WorkflowCheckpoint] = field(default_factory=dict)

    def plan(self, task: str, agents: list[str] | None = None, require_human_review: bool = False) -> dict[str, Any]:
        agents = agents or ["architect", "implementer", "reviewer"]
        checkpoint_id = f"checkpoint-{len(self.checkpoints) + 1}"
        state = {
            "task": task,
            "agents": agents,
            "next_agent": agents[0],
            "steps": [{"agent": agent, "action": f"handle:{task}", "status": "queued"} for agent in agents],
            "human_review_required": require_human_review,
        }
        status: Literal["planned", "paused"] = "paused" if require_human_review else "planned"
        checkpoint = WorkflowCheckpoint(checkpoint_id, task, state, status)
        checkpoint.event_log.append(MessageEvent(kind="workflow.created", payload={"task": task, "agents": agents}, role="system"))
        if require_human_review:
            checkpoint.event_log.append(MessageEvent(kind="workflow.interrupt", payload={"reason": "human_review_required", "checkpoint": checkpoint_id}, role="assistant"))
        self.checkpoints[checkpoint_id] = checkpoint
        return checkpoint.to_dict()

    def recover(self, checkpoint: str) -> dict[str, Any]:
        workflow = self.checkpoints[checkpoint]
        workflow.status = "recovered"
        workflow.event_log.append(MessageEvent(kind="workflow.recovered", payload={"checkpoint": checkpoint}, role="system"))
        return workflow.to_dict()

    def resume(self, checkpoint: str, human_input: dict[str, Any]) -> dict[str, Any]:
        workflow = self.checkpoints[checkpoint]
        workflow.state["human_input"] = human_input
        workflow.status = "running"
        workflow.event_log.append(MessageEvent(kind="workflow.resumed", payload=human_input, role="user"))
        return workflow.to_dict()

    def stream_events(self, checkpoint: str) -> list[dict[str, Any]]:
        return self.checkpoints[checkpoint].event_log.all()
