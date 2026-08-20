from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Literal

from .catalog import PLATFORM_LEVELS


IMPLEMENTATION_MODULES = {
    0: "agi_platform.llm.core",
    1: "agi_platform.memory.core",
    2: "agi_platform.guardian.core",
    3: "agi_platform.research.core",
    4: "agi_platform.chinese_hub.core",
    5: "agi_platform.analysis.core",
    6: "agi_platform.github_intel.core",
    7: "agi_platform.sandbox.core",
    8: "agi_platform.knowledge_graph.core",
    9: "agi_platform.orchestration",
    10: "agi_platform.governance.core",
    11: "agi_platform.evolution.core",
}

Status = Literal["GREEN", "YELLOW", "RED"]


@dataclass(frozen=True)
class ReadinessCriterion:
    name: str
    passed: bool
    detail: str
    critical: bool = False


@dataclass(frozen=True)
class ControlAssessment:
    name: str
    status: Status
    evidence: str
    required_fix: str
    critical: bool = False


CRITICAL_CONTROLS: dict[int, tuple[ControlAssessment, ...]] = {
    0: (
        ControlAssessment("provider_resilience", "YELLOW", "LLMCore uses httpx timeouts but lacks retry/circuit-breaker and policy-aware routing.", "Add provider health, retry budget, circuit breaker, cost and policy-aware router.", True),
        ControlAssessment("durable_usage_accounting", "RED", "LLMCore.usage is in-process memory.", "Persist usage/cost records transactionally.", True),
    ),
    1: (ControlAssessment("durable_memory", "YELLOW", "MemoryLayer persists canonical metadata through SQLAlchemy/PostgreSQL-compatible tables; Qdrant remains an optional vector dependency.", "Add production Qdrant health enforcement and PostgreSQL RLS policies.", True),),
    2: (ControlAssessment("immutable_memory_audit", "RED", "MemoryGuardian audit/reviews/versions are in-process containers.", "Persist immutable audit events and guarded memory versions.", True),),
    3: (ControlAssessment("safe_external_research", "YELLOW", "ResearchLayer has timeouts but no SSRF/size/content-type policy.", "Add SSRF controls, response limits, source policy and evidence persistence.", True),),
    4: (ControlAssessment("translation_provenance", "YELLOW", "ChineseResearchHub keeps original/translated fields but no durable evidence/version model.", "Persist original/translation/evidence records with provider/version metadata.", True),),
    5: (ControlAssessment("analysis_finding_model", "YELLOW", "Analysis findings are deterministic but lack stable finding_id/fingerprint/status persistence.", "Add canonical finding schema, fingerprints, status lifecycle and persistence.", True),),
    6: (ControlAssessment("bounded_repository_indexing", "YELLOW", "GitHubIntelligence fetches repo/contributors with timeout but no pagination/rate-limit checkpointing.", "Add incremental indexing, pagination, content hashes and rate-limit handling.", True),),
    7: (ControlAssessment("strong_sandbox_isolation", "RED", "SandboxLab still uses subprocess; resource limits help but are not container/microVM isolation.", "Execute untrusted workloads in non-root container/microVM with network/filesystem isolation and escape tests.", True),),
    8: (ControlAssessment("durable_graph", "RED", "KnowledgeGraph.nodes/edges are in-process containers.", "Persist graph entities/relationships in Neo4j with tenant constraints and traversal limits.", True),),
    9: (ControlAssessment("durable_workflow_engine", "YELLOW", "WorkflowStateStore persists runs/tasks/checkpoints/events in SQL with leases and idempotency keys; full worker side-effect execution is still a later phase.", "Add production worker scheduler and external side-effect execution records.", True),),
    10: (ControlAssessment("approval_governance", "RED", "ArchitectureGovernance decisions/reviews are in-process and low-risk auto-approval lacks scoped approval records.", "Persist ADR records and enforce explicit approval gates for high-risk actions.", True),),
    11: (ControlAssessment("self_improvement_gate", "YELLOW", "SelfImprovementEngine only proposes; no mutation path exists, but no formal approval lifecycle is enforced.", "Model proposal/benchmark/approval/deploy/rollback lifecycle with policy gates.", True),),
}


def level_readiness() -> list[dict]:
    results: list[dict] = []
    for level in PLATFORM_LEVELS:
        module_name = IMPLEMENTATION_MODULES[level.level]
        criteria = [
            _module_imports(module_name),
            ReadinessCriterion("api_surface", bool(level.api), ", ".join(level.api)),
            ReadinessCriterion("database_schema_declared", bool(level.database), ", ".join(level.database)),
            ReadinessCriterion("observability_declared", bool(level.metrics), ", ".join(level.metrics)),
            ReadinessCriterion("security_controls_declared", bool(level.security), ", ".join(level.security)),
        ]
        controls = CRITICAL_CONTROLS[level.level]
        status = _status(criteria, controls)
        results.append({
            "level": level.level,
            "name": level.name,
            "status": status,
            "criteria": [item.__dict__ for item in criteria],
            "controls": [item.__dict__ for item in controls],
        })
    return results


def platform_ready() -> dict:
    levels = level_readiness()
    if any(level["status"] == "RED" for level in levels):
        status = "not-ready"
    elif any(level["status"] == "YELLOW" for level in levels):
        status = "degraded"
    else:
        status = "ready"
    return {"status": status, "levels": levels}


def _status(criteria: list[ReadinessCriterion], controls: tuple[ControlAssessment, ...]) -> Status:
    if any(not item.passed and item.critical for item in criteria):
        return "RED"
    if any(control.status == "RED" and control.critical for control in controls):
        return "RED"
    if any(not item.passed for item in criteria) or any(control.status == "YELLOW" for control in controls):
        return "YELLOW"
    return "GREEN"


def _module_imports(module_name: str) -> ReadinessCriterion:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        return ReadinessCriterion("implementation_import", False, str(exc), critical=True)
    return ReadinessCriterion("implementation_import", True, module_name, critical=True)
