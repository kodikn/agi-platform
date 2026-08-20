from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class PlatformLevel:
    level: int
    name: str
    purpose: str
    modules: tuple[str, ...]
    api: tuple[str, ...]
    database: tuple[str, ...]
    metrics: tuple[str, ...]
    security: tuple[str, ...]


PLATFORM_LEVELS: Final[tuple[PlatformLevel, ...]] = (
    PlatformLevel(0, "LLM Core", "Unified access to model providers with routing, failover, usage accounting, and validation.", ("llm/providers", "llm/router", "llm/registry", "llm/telemetry"), ("/chat", "/completion", "/embeddings", "/models"), ("models", "providers", "usage", "costs"), ("tokens_used", "cost", "latency", "errors"), ("provider credential isolation", "request validation", "rate limiting")),
    PlatformLevel(1, "Memory Layer", "Enterprise memory storage, retrieval, ranking, consolidation, expiration, and search.", ("memory/episodic", "memory/semantic", "memory/working", "memory/retrieval", "memory/ranking"), ("/memory/store", "/memory/search", "/memory/retrieve"), ("memories", "memory_embeddings", "memory_archives"), ("memory_search_latency", "memories_stored"), ("tenant scoping", "content classification", "retention policies")),
    PlatformLevel(2, "Memory Guardian", "Governance controls for memory quality, review, rollback, audit, and trust scoring.", ("guardian/validator", "guardian/approval", "guardian/audit", "guardian/rollback"), ("/guardian/review", "/guardian/audit"), ("memory_audit", "memory_versions", "memory_reviews"), ("review_queue_depth", "memory_risk_score"), ("human approval gates", "immutable audit trail", "rollback authorization")),
    PlatformLevel(3, "Research Layer", "Evidence collection, source validation, trust ranking, reporting, and threat extraction.", ("research/collectors", "research/ranking", "research/evidence", "research/reports"), ("/research/query", "/research/report"), ("research_sources", "evidence", "research_reports"), ("source_trust", "report_latency"), ("source allowlists", "evidence provenance", "malicious content isolation")),
    PlatformLevel(4, "Chinese Research Hub", "Chinese-language ingestion, translation, classification, NER, IOC extraction, and enrichment.", ("chinese_hub/ingestion", "chinese_hub/translation", "chinese_hub/extraction", "chinese_hub/enrichment"), ("/chinese/articles", "/chinese/analyze"), ("chinese_articles", "translations", "extracted_iocs"), ("translation_latency", "iocs_extracted"), ("original-source preservation", "translation traceability", "content safety checks")),
    PlatformLevel(5, "Analysis Layer", "Static, dependency, architecture, security, and code-quality analysis.", ("analysis/static", "analysis/dependency", "analysis/architecture", "analysis/security"), ("/analyze/code", "/analyze/repository"), ("analysis_runs", "analysis_findings"), ("findings_count", "analysis_runtime"), ("sandboxed scanners", "repository allowlists", "secret redaction")),
    PlatformLevel(6, "GitHub Intelligence", "Repository indexing, commit/issue/PR analysis, contributor graphing, and knowledge extraction.", ("github_intel/indexing", "github_intel/commits", "github_intel/issues", "github_intel/prs", "github_intel/graph"), ("/github/repositories", "/github/analyze"), ("repositories", "commits", "issues", "pull_requests", "dependencies"), ("repos_indexed", "github_api_errors"), ("token least privilege", "webhook signature validation", "PII minimization")),
    PlatformLevel(7, "Sandbox Lab", "Secure execution with Docker isolation, artifacts, limits, policies, monitoring, and cleanup.", ("sandbox/runtime", "sandbox/monitor", "sandbox/artifacts", "sandbox/cleanup"), ("/sandbox/execute", "/sandbox/artifacts"), ("sandbox_runs", "sandbox_artifacts"), ("cpu", "memory", "network", "runtime"), ("network policies", "resource quotas", "workspace isolation")),
    PlatformLevel(8, "Knowledge Graph", "Neo4j-backed entity, memory, research, repository, threat, and agent graphs.", ("knowledge_graph/entities", "knowledge_graph/relationships", "knowledge_graph/analytics", "knowledge_graph/queries"), ("/graph/search", "/graph/traverse"), ("graph_entities", "graph_relationships"), ("graph_query_latency", "relationships_discovered"), ("relationship ACLs", "query limits", "tenant labels")),
    PlatformLevel(9, "Orchestrator", "LangGraph-ready workflow, routing, checkpointing, recovery, human-in-loop, retry, and context routing.", ("orchestrator/workflows", "orchestrator/routing", "orchestrator/checkpointing", "orchestrator/recovery"), ("/orchestrate", "/workflows"), ("workflow_runs", "workflow_checkpoints"), ("workflow_success_rate", "retry_count"), ("workflow policy enforcement", "human approval checkpoints", "tool permissions")),
    PlatformLevel(10, "Architecture Governance", "Architecture proposal, decision, review, approval, risk, and version governance.", ("governance/proposals", "governance/decisions", "governance/reviews", "governance/approvals"), ("/governance/proposals", "/governance/decisions"), ("architecture_decisions", "architecture_reviews"), ("approval_latency", "risk_score"), ("segregation of duties", "ADR immutability", "risk acceptance records")),
    PlatformLevel(11, "Self Improvement", "Telemetry analysis, evaluation, pattern discovery, optimization suggestions, and improvement proposals.", ("evolution/telemetry", "evolution/evaluation", "evolution/optimization", "evolution/learning"), ("/evolution/proposals", "/evolution/evaluate"), ("improvement_proposals", "evaluation_runs"), ("success_rate", "failure_rate", "tool_effectiveness", "agent_effectiveness"), ("proposal approval gates", "experiment isolation", "regression checks")),
)


def get_level(level: int) -> PlatformLevel:
    for item in PLATFORM_LEVELS:
        if item.level == level:
            return item
    raise KeyError(f"Unknown platform level: {level}")
