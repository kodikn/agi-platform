from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CompetitiveStrength:
    source: str
    strength: str
    adopted_as: str
    platform_level: int
    runtime_capability: str


COMPETITIVE_STRENGTHS: tuple[CompetitiveStrength, ...] = (
    CompetitiveStrength("LangGraph", "stateful graph orchestration, checkpoints, recovery", "checkpointed workflow graph planning", 9, "workflow_graph"),
    CompetitiveStrength("CrewAI", "role-based crews and event-driven flows", "crew/role task routing", 9, "crew_flow"),
    CompetitiveStrength("AutoGen", "multi-agent conversation programming", "agent handoff trace", 9, "agent_conversation"),
    CompetitiveStrength("AutoGPT", "tool ecosystem and marketplace-style extensibility", "tool capability hints", 0, "tool_marketplace"),
    CompetitiveStrength("MetaGPT", "software-company SOP roles", "architect/implementer/reviewer SOP stages", 9, "sop_roles"),
    CompetitiveStrength("ChatDev", "zero-code workflow description", "declarative workflow contract", 9, "zero_code_contract"),
    CompetitiveStrength("FastAPI LangGraph template", "production backend controls", "probes, metrics, auth policy, and deployment hardening", 9, "production_backend"),
)


def competitive_strengths() -> list[dict]:
    return [asdict(item) for item in COMPETITIVE_STRENGTHS]


def capability_names() -> list[str]:
    return [item.runtime_capability for item in COMPETITIVE_STRENGTHS]
