from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol


class ServiceProbe(Protocol):
    def health(self) -> dict[str, Any]: ...
    def levels(self) -> list[dict[str, Any]]: ...
    def external_memory_health(self) -> dict[str, Any]: ...


@dataclass
class ArchitectureAutonomyController:
    """Runs safe self-tests and creates approval-gated architecture proposals."""

    proposals: list[dict[str, Any]] = field(default_factory=list)

    def self_test(self, service: ServiceProbe) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        started = time.perf_counter()

        health = service.health()
        checks.append({"name": "service_health", "status": "passed" if health.get("status") == "ok" else "failed", "detail": health})

        levels = service.levels() if hasattr(service, "levels") else []
        checks.append({"name": "level_catalog", "status": "passed" if len(levels) >= 12 else "failed", "detail": {"levels": len(levels)}})

        models = service.llm.models() if hasattr(service, "llm") else {"providers": {}}
        configured_models = [name for name, provider in models.get("providers", {}).items() if provider.get("configured")]
        checks.append({"name": "model_provider", "status": "passed" if configured_models else "needs-configuration", "detail": {"configured": configured_models}})

        external_memory = service.external_memory_health() if hasattr(service, "external_memory_health") else {"status": "unknown"}
        checks.append({"name": "external_memory", "status": external_memory.get("status", "unknown"), "detail": external_memory})

        overall = "passed" if all(check["status"] in {"passed", "disabled", "ok"} for check in checks) else "needs-attention"
        return {"status": overall, "checks": checks, "duration_ms": round((time.perf_counter() - started) * 1000, 3)}

    def propose_improvements(self, self_test_report: dict[str, Any], governance) -> dict[str, Any]:
        proposals = []
        for check in self_test_report.get("checks", []):
            if check.get("status") in {"passed", "disabled", "ok"}:
                continue
            title = f"Address {check['name']} self-test finding"
            body = f"Self-test status: {check['status']}. Detail: {check.get('detail', {})}. Proposed changes require explicit human approval before implementation."
            existing = next((proposal for proposal in self.proposals if proposal["source_check"] == check["name"] and proposal["status"] == "needs-review"), None)
            if existing:
                proposals.append(existing)
                continue
            decision = governance.propose(title, body, risk_score=0.7)
            proposal = {"decision_id": decision["id"], "title": title, "status": decision["status"], "approval_required": True, "source_check": check["name"]}
            self.proposals.append(proposal)
            proposals.append(proposal)
        return {"proposals": proposals, "count": len(proposals), "approval_required": True, "auto_apply": False}
