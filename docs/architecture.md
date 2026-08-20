# AGI Platform Architecture

The platform is organized into twelve delivery levels so implementation can proceed incrementally without losing architectural context.

## System Flow

```text
User -> Level 9 Orchestrator -> Levels 0,1,2,3,4,5,6,7,8 -> Level 10 Governance -> Level 11 Self Improvement
```

## Production Readiness Contract

Every level includes an executable Python implementation, API surface, tests, schema ownership, observability metrics, security controls, and documentation before it is considered complete.

## Implemented Levels

| Level | Module | Runtime implementation |
| --- | --- | --- |
| 0 | `agi_platform.llm.core` | Provider/model registry, routing, provider-backed completion, embeddings, caching, usage and latency metrics. |
| 1 | `agi_platform.memory.core` | Typed memory records, search ranking, consolidation, and archive-ready metadata. |
| 2 | `agi_platform.guardian.core` | Duplicate-risk validation, review decisions, version history, rollback, and audit entries. |
| 3 | `agi_platform.research.core` | Multi-source evidence collection, trust ranking, IOC extraction, and report persistence. |
| 4 | `agi_platform.chinese_hub.core` | Simplified/traditional article ingestion, configured LibreTranslate-based translation terms, classification, IOC extraction, and original/translated storage. |
| 5 | `agi_platform.analysis.core` | Python syntax validation, static security rules, repository file analysis, and finding metrics. |
| 6 | `agi_platform.github_intel.core` | GitHub repository indexing, dependency inventory, and repository knowledge extraction. |
| 7 | `agi_platform.sandbox.core` | Policy-restricted command execution, temporary workspace isolation, runtime metrics, and cleanup. |
| 8 | `agi_platform.knowledge_graph.core` | Entity upsert, relationship creation, graph search, and relationship traversal. |
| 9 | `agi_platform.orchestration` | Multi-agent workflow planning, checkpoint assignment, and recovery lookup. |
| 10 | `agi_platform.governance.core` | Architecture proposals, risk scoring, approval state, and review records. |
| 11 | `agi_platform.evolution.core` | Telemetry evaluation, success/failure/tool/agent metrics, and automatic improvement proposals. |
