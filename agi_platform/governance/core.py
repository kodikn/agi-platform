from __future__ import annotations

from dataclasses import dataclass, field

from agi_platform.security import TenantContext


@dataclass
class ArchitectureGovernance:
    decisions: list[dict] = field(default_factory=list)
    reviews: list[dict] = field(default_factory=list)

    def propose(self, title: str, body: str, risk_score: float = 0.0, context: TenantContext | None = None) -> dict:
        if context is None:
            raise ValueError("tenant context is required")
        tenant_decisions = [decision for decision in self.decisions if decision.get("tenant_id") == context.tenant_id]
        decision = {"id": len(tenant_decisions) + 1, "tenant_id": context.tenant_id, "actor": context.subject, "title": title, "body": body, "risk_score": risk_score, "status": "needs-review" if risk_score >= 0.5 else "approved"}
        self.decisions.append(decision)
        return decision

    def review(self, decision_id: int, approver: str, approved: bool, context: TenantContext | None = None) -> dict:
        if context is None:
            raise ValueError("tenant context is required")
        decision = next((item for item in self.decisions if item.get("tenant_id") == context.tenant_id and item.get("id") == decision_id), None)
        if decision is None:
            raise KeyError("decision not found for tenant")
        decision["status"] = "approved" if approved else "rejected"
        review = {"tenant_id": context.tenant_id, "decision_id": decision_id, "approver": approver, "approved": approved}
        self.reviews.append(review)
        return review
