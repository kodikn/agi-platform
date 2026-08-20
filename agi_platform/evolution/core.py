from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

LifecycleState = Literal[
    "PROPOSAL",
    "EVALUATION",
    "BENCHMARK",
    "RISK_ASSESSMENT",
    "APPROVAL",
    "SANDBOX",
    "CANARY",
    "DEPLOY",
    "MONITOR",
    "ROLLBACK",
]
PROTECTED_ACTIONS = {
    "deploy",
    "modify_production",
    "modify_security_policy",
    "modify_authorization",
    "access_credentials",
}


@dataclass
class SelfImprovementEngine:
    evaluations: list[dict[str, Any]] = field(default_factory=list)
    proposals: dict[str, dict[str, Any]] = field(default_factory=dict)
    benchmarks: dict[str, dict[str, Any]] = field(default_factory=dict)
    risk_assessments: dict[str, dict[str, Any]] = field(default_factory=dict)
    approvals: dict[str, dict[str, Any]] = field(default_factory=dict)
    deployments: dict[str, dict[str, Any]] = field(default_factory=dict)
    rollbacks: dict[str, dict[str, Any]] = field(default_factory=dict)
    audit_events: list[dict[str, Any]] = field(default_factory=list)

    def evaluate(self, metrics: dict[str, float]) -> dict[str, Any]:
        success_rate = metrics.get("success_rate", 1.0)
        failure_rate = metrics.get("failure_rate", max(0.0, 1.0 - success_rate))
        proposals = []
        if failure_rate > 0.05:
            proposals.append(
                {
                    "title": "Reduce workflow failure rate",
                    "priority": "high",
                    "expected_metric": "failure_rate",
                }
            )
        if metrics.get("tool_effectiveness", 1.0) < 0.8:
            proposals.append(
                {
                    "title": "Re-rank low-performing tools",
                    "priority": "medium",
                    "expected_metric": "tool_effectiveness",
                }
            )
        result = {
            "metrics": metrics,
            "proposals": proposals,
            "agent_effectiveness": metrics.get("agent_effectiveness", success_rate),
        }
        self.evaluations.append(result)
        return result

    def create_proposal(
        self,
        tenant_id: str,
        actor_id: str,
        title: str,
        change: dict[str, Any],
        risk: str = "low",
    ) -> dict[str, Any]:
        proposal_id = f"sip-{len(self.proposals) + 1}"
        record = {
            "id": proposal_id,
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "title": title,
            "change": change,
            "risk": risk,
            "state": "PROPOSAL",
            "created_at": int(time.time()),
        }
        self.proposals[proposal_id] = record
        self._audit(tenant_id, actor_id, "proposal.create", proposal_id, "allowed")
        return record

    def record_benchmark(
        self, proposal_id: str, metrics: dict[str, float]
    ) -> dict[str, Any]:
        proposal = self._proposal(proposal_id)
        proposal["state"] = "BENCHMARK"
        benchmark = {
            "proposal_id": proposal_id,
            "tenant_id": proposal["tenant_id"],
            "metrics": metrics,
            "passed": metrics.get("success_rate", 0) >= 0.95
            and metrics.get("failure_rate", 1) <= 0.02,
        }
        self.benchmarks[proposal_id] = benchmark
        self._audit(
            proposal["tenant_id"],
            proposal["actor_id"],
            "benchmark.record",
            proposal_id,
            "allowed",
        )
        return benchmark

    def assess_risk(
        self, proposal_id: str, findings: list[str], high_risk: bool
    ) -> dict[str, Any]:
        proposal = self._proposal(proposal_id)
        proposal["state"] = "RISK_ASSESSMENT"
        assessment = {
            "proposal_id": proposal_id,
            "tenant_id": proposal["tenant_id"],
            "findings": findings,
            "high_risk": high_risk,
            "requires_approval": high_risk,
        }
        self.risk_assessments[proposal_id] = assessment
        self._audit(
            proposal["tenant_id"],
            proposal["actor_id"],
            "risk.assess",
            proposal_id,
            "allowed",
        )
        return assessment

    def approve(
        self, proposal_id: str, tenant_id: str, approver_id: str, expires_at: int
    ) -> dict[str, Any]:
        proposal = self._proposal(proposal_id)
        if tenant_id != proposal["tenant_id"]:
            self._audit(
                tenant_id, approver_id, "approval.create", proposal_id, "denied"
            )
            raise PermissionError("wrong tenant approval")
        approval = {
            "proposal_id": proposal_id,
            "tenant_id": tenant_id,
            "approver_id": approver_id,
            "expires_at": expires_at,
            "approved_at": int(time.time()),
        }
        self.approvals[proposal_id] = approval
        proposal["state"] = "APPROVAL"
        self._audit(tenant_id, approver_id, "approval.create", proposal_id, "allowed")
        return approval

    def deploy(
        self,
        proposal_id: str,
        tenant_id: str,
        actor_id: str,
        canary_passed: bool = False,
    ) -> dict[str, Any]:
        proposal = self._proposal(proposal_id)
        if tenant_id != proposal["tenant_id"]:
            self._audit(tenant_id, actor_id, "deployment.deploy", proposal_id, "denied")
            raise PermissionError("wrong tenant deployment")
        if any(
            action in PROTECTED_ACTIONS
            for action in proposal.get("change", {}).get("actions", [])
        ):
            approval = self.approvals.get(proposal_id)
            if not approval or approval["expires_at"] <= int(time.time()):
                self._audit(
                    tenant_id, actor_id, "deployment.deploy", proposal_id, "denied"
                )
                raise PermissionError("valid explicit approval required")
        if not self.benchmarks.get(proposal_id, {}).get("passed"):
            self._audit(tenant_id, actor_id, "deployment.deploy", proposal_id, "denied")
            raise RuntimeError("benchmark gate failed")
        if not canary_passed:
            proposal["state"] = "ROLLBACK"
            rollback = {
                "proposal_id": proposal_id,
                "tenant_id": tenant_id,
                "reason": "failed canary",
                "created_at": int(time.time()),
            }
            self.rollbacks[proposal_id] = rollback
            self._audit(
                tenant_id, actor_id, "deployment.rollback", proposal_id, "allowed"
            )
            return rollback
        deployment = {
            "proposal_id": proposal_id,
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "state": "MONITOR",
            "deployed_at": int(time.time()),
        }
        self.deployments[proposal_id] = deployment
        proposal["state"] = "MONITOR"
        self._audit(tenant_id, actor_id, "deployment.deploy", proposal_id, "allowed")
        return deployment

    def _proposal(self, proposal_id: str) -> dict[str, Any]:
        if proposal_id not in self.proposals:
            raise KeyError(proposal_id)
        return self.proposals[proposal_id]

    def _audit(
        self, tenant_id: str, actor_id: str, action: str, resource_id: str, result: str
    ) -> None:
        self.audit_events.append(
            {
                "tenant_id": tenant_id,
                "actor_id": actor_id,
                "action": action,
                "resource_id": resource_id,
                "result": result,
                "created_at": int(time.time()),
            }
        )
