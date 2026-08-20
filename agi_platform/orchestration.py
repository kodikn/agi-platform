from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WorkflowEngine:
    runs: list[dict] = field(default_factory=list)

    def plan(self, task: str, agents: list[str] | None = None) -> dict:
        agents = agents or ["architect", "implementer", "reviewer"]
        steps = [{"agent": agent, "action": f"{agent} handles {task}", "status": "queued"} for agent in agents]
        workflow = {"task": task, "steps": steps, "checkpoint": f"checkpoint-{len(self.runs) + 1}", "status": "planned"}
        self.runs.append(workflow)
        return workflow

    def recover(self, checkpoint: str) -> dict:
        for run in self.runs:
            if run["checkpoint"] == checkpoint:
                return {**run, "status": "recovered"}
        raise KeyError(f"checkpoint {checkpoint} not found")
