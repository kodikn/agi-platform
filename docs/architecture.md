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


## Порівняння з цільовою production-рівневою структурою

Каталог тепер відображає запитане дерево модулів для Level 0-11. Поточні runtime-реалізації залишаються консолідованими Python-модулями, а публічний архітектурний каталог показує цільові межі модулів, які можна розгорнути в окремі каталоги та технічні задачі.

| Рівень | Цільові модулі в каталозі | Поточна runtime-реалізація | Примітки щодо відповідності |
| --- | --- | --- | --- |
| 0 — LLM Core | `providers/`, `router/`, `registry/`, `telemetry/` | `agi_platform.llm.core` | Покриває адаптери провайдерів, маршрутизацію та failover моделей, metadata реєстру моделей і telemetry використання. |
| 1 — Memory Layer | `working_memory/`, `episodic_memory/`, `semantic_memory/`, `retrieval/`, `consolidation/` | `agi_platform.memory.core` | Покриває активний контекст, історію подій, факти/сутності, пошук, reranking і консолідацію пам’яті. |
| 2 — Memory Guardian | `validator/`, `deduplication/`, `approval/`, `audit/`, `rollback/` | `agi_platform.guardian.core` | Покриває validation, перевірку дублікатів, approval workflow, audit history і rollback controls. |
| 3 — Research Layer | `collectors/`, `extraction/`, `ranking/`, `reporting/` | `agi_platform.research.core` | Покриває збір джерел, entity/IOC extraction, trust/relevance ranking і генерацію звітів. |
| 4 — Chinese Research Hub | `ingestion/`, `translation/`, `classification/`, `threat_extraction/`, `enrichment/` | `agi_platform.chinese_hub.core` | Покриває ingestion китайських джерел, translation, classification, cyber-threat extraction і enrichment records. |
| 5 — Analysis Layer | `static_analysis/`, `dependency_analysis/`, `architecture_analysis/`, `security_analysis/`, `repository_analysis/` | `agi_platform.analysis.core` | Покриває статичний аналіз коду, dependency inventory, architectural findings, security risks і repository-level analysis. |
| 6 — GitHub Intelligence | `repository_indexer/`, `commit_analyzer/`, `issue_analyzer/`, `pr_analyzer/`, `dependency_graph/`, `knowledge_extractor/` | `agi_platform.github_intel.core` | Покриває індексацію репозиторіїв, цільові analyzers і knowledge extraction boundaries. |
| 7 — Sandbox Lab | `runtime/`, `isolation/`, `monitoring/`, `artifacts/`, `cleanup/` | `agi_platform.sandbox.core` | Покриває safe execution, workspace/container isolation, runtime monitoring, artifacts і cleanup. |
| 8 — Knowledge Graph | `entities/`, `relationships/`, `graph_store/`, `graph_search/`, `analytics/` | `agi_platform.knowledge_graph.core` | Покриває entities, relationships, Neo4j-oriented storage, graph search і analytics. |
| 9 — Orchestrator | `workflow_engine/`, `task_router/`, `agent_router/`, `checkpoint_manager/`, `recovery_manager/`, `planner/` | `agi_platform.orchestration` | Покриває workflow execution, task/agent routing, checkpointing, recovery і planning. |
| 10 — Architecture Governance | `proposals/`, `decisions/`, `reviews/`, `risk_management/`, `approvals/` | `agi_platform.governance.core` | Покриває proposals, ADR-style decisions, reviews, risk scoring і approvals. |
| 11 — Self Improvement | `telemetry/`, `evaluation/`, `optimization/`, `learning/`, `pattern_discovery/`, `improvement_engine/` | `agi_platform.evolution.core` | Покриває metric collection, evaluation, optimization, learning, pattern discovery і generated improvements. |

## Цільовий головний потік системи

```text
User
  │
  ▼
Level 9 Orchestrator
  │
  ├── Level 0 LLM Core
  ├── Level 1 Memory
  ├── Level 2 Guardian
  ├── Level 3 Research
  ├── Level 5 Analysis
  ├── Level 6 GitHub Intel
  ├── Level 7 Sandbox
  └── Level 8 Knowledge Graph
          │
          ▼
Level 10 Governance
          │
          ▼
Level 11 Self Improvement
```


## Запозичені сильні сторони з GitHub-аналогів

Платформа додає найсильніші ідеї з провідних open-source agent projects як runtime capabilities, а не лише як roadmap:

| Джерело | Сильна сторона | Як додано в AGI Platform |
| --- | --- | --- |
| LangGraph | Stateful graph orchestration, checkpoints, recovery | `POST /orchestrate` повертає `graph` із nodes, edges, checkpoint і recovery flag. |
| CrewAI | Role-based crews and flows | Workflow містить `crew` із agents і flow `plan -> execute -> review -> govern`. |
| AutoGen | Multi-agent conversation programming | Workflow містить `conversation` handoff trace між user і agents. |
| AutoGPT | Tool ecosystem / marketplace extensibility | Capability catalog містить `tool_marketplace` як platform extension point. |
| MetaGPT | Software-company SOP roles | Default agents отримують architect/implementer/reviewer SOP roles. |
| ChatDev | Zero-code workflow description | Workflow містить `zero_code_contract`, який можна згенерувати з UI або declarative builder. |
| FastAPI LangGraph template | Production backend controls | Deployment і API використовують probes, metrics, auth policy і hardened manifests. |

Ці capabilities доступні через `GET /architecture/competitive-advantages` і додаються до кожного нового workflow у полі `competitive_capabilities`.
