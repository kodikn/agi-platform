from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ArchitectureGovernance:
    decisions: list[dict] = field(default_factory=list)
    reviews: list[dict] = field(default_factory=list)

    def propose(self, title: str, body: str, risk_score: float = 0.0) -> dict:
        decision = {"id": len(self.decisions) + 1, "title": title, "body": body, "risk_score": risk_score, "status": "needs-review" if risk_score >= 0.5 else "approved"}
        self.decisions.append(decision)
        return decision

    def review(self, decision_id: int, approver: str, approved: bool) -> dict:
        decision = self.decisions[decision_id - 1]
        decision["status"] = "approved" if approved else "rejected"
        review = {"decision_id": decision_id, "approver": approver, "approved": approved}
        self.reviews.append(review)
        return review
