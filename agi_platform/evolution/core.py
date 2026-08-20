from __future__ import annotations

from dataclasses import dataclass, field

from agi_platform.security import TenantContext


@dataclass
class SelfImprovementEngine:
    evaluations: list[dict] = field(default_factory=list)

    def evaluate(self, metrics: dict[str, float], context: TenantContext | None = None) -> dict:
        if context is None:
            raise ValueError("tenant context is required")
        success_rate = metrics.get("success_rate", 1.0)
        failure_rate = metrics.get("failure_rate", max(0.0, 1.0 - success_rate))
        proposals = []
        if failure_rate > 0.05:
            proposals.append({"title": "Reduce workflow failure rate", "priority": "high", "expected_metric": "failure_rate"})
        if metrics.get("tool_effectiveness", 1.0) < 0.8:
            proposals.append({"title": "Re-rank low-performing tools", "priority": "medium", "expected_metric": "tool_effectiveness"})
        result = {"tenant_id": context.tenant_id, "metrics": metrics, "proposals": proposals, "agent_effectiveness": metrics.get("agent_effectiveness", success_rate)}
        self.evaluations.append(result)
        return result
