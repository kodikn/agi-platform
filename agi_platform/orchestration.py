from __future__ import annotations

from dataclasses import dataclass, field

from .competitive import COMPETITIVE_STRENGTHS, capability_names


@dataclass
class WorkflowEngine:
    runs: list[dict] = field(default_factory=list)

    def plan(self, task: str, agents: list[str] | None = None) -> dict:
        agents = agents or ["architect", "implementer", "reviewer"]
        checkpoint = f"checkpoint-{len(self.runs) + 1}"
        steps = [
            {
                "agent": agent,
                "role": self._role_for(agent),
                "action": f"{agent} handles {task}",
                "status": "queued",
            }
            for agent in agents
        ]
        workflow = {
            "task": task,
            "steps": steps,
            "checkpoint": checkpoint,
            "status": "planned",
            "graph": self._workflow_graph(checkpoint, steps),
            "conversation": self._handoff_trace(steps),
            "crew": {"name": "production-delivery-crew", "agents": agents, "flow": "plan -> execute -> review -> govern"},
            "zero_code_contract": {"task": task, "agents": agents, "approval_required": True},
            "competitive_capabilities": capability_names(),
        }
        self.runs.append(workflow)
        return workflow

    def _role_for(self, agent: str) -> str:
        roles = {
            "architect": "designs the workflow and constraints",
            "implementer": "executes the approved implementation steps",
            "reviewer": "validates quality, safety, and production readiness",
        }
        return roles.get(agent, "specialized execution agent")

    def _workflow_graph(self, checkpoint: str, steps: list[dict]) -> dict:
        nodes = [step["agent"] for step in steps]
        edges = [{"from": source, "to": target} for source, target in zip(nodes, nodes[1:])]
        return {"checkpoint": checkpoint, "nodes": nodes, "edges": edges, "recovery_enabled": True}

    def _handoff_trace(self, steps: list[dict]) -> list[dict]:
        return [
            {"from": steps[index - 1]["agent"] if index else "user", "to": step["agent"], "message": step["action"]}
            for index, step in enumerate(steps)
        ]

    def competitive_blueprint(self) -> list[dict]:
        return [strength.__dict__ for strength in COMPETITIVE_STRENGTHS]

    def recover(self, checkpoint: str) -> dict:
        for run in self.runs:
            if run["checkpoint"] == checkpoint:
                return {**run, "status": "recovered"}
        raise KeyError(f"checkpoint {checkpoint} not found")
