# TencentDB Agent Memory integration proposal

## What TencentDB Agent Memory adds

TencentDB Agent Memory is a team-level memory hub for AI agents. It turns conversations, documents, and code into reusable assets that can be governed, shared, and equipped across different agent frameworks. The repository describes four core asset categories that map well to this platform: Chat Memory, Skills, Wiki, and CodeGraph.

Key capabilities to adopt or integrate:

- **Chat Memory:** persistent user, team, decision, preference, and interaction context.
- **Skill assets:** reusable workflows with versions, trigger boundaries, execution steps, resources, and validation rules.
- **Wiki assets:** structured knowledge pages generated from documents, specs, runbooks, and files.
- **CodeGraph assets:** indexed files, symbols, call relationships, and impact paths for safer code changes.
- **Memory Hub control plane:** ownership, versions, status, visibility, usage counts, agent bindings, and human review.
- **Proxy-based agent compatibility:** agents can point to the memory proxy without per-agent plugins.
- **Layered retrieval:** L0 conversations, L1 atoms, L2 scenarios, and L3 core/persona memories, with BM25/vector/RRF fallback.

## Fit with AGI Platform

AGI Platform already has levels for memory, guardian review, research, analysis, GitHub intelligence, knowledge graph, orchestration, governance, and self-improvement. TencentDB Agent Memory should not replace these levels. It should become a specialized external team-memory backend that strengthens Level 1, Level 2, Level 6, Level 8, and Level 9.

| AGI Platform level | Current role | TencentDB integration |
| --- | --- | --- |
| Level 1 Memory Layer | Store/search/consolidate local memories | Add external team-memory read/write connector and asset lifecycle sync. |
| Level 2 Memory Guardian | Validate, version, rollback, audit | Map Memory Hub review/status/visibility into guardian reviews and audit events. |
| Level 6 GitHub Intelligence | Index repositories and dependencies | Export repository analysis into CodeGraph-compatible assets; ingest CodeGraph impact paths. |
| Level 8 Knowledge Graph | Entity and relationship graph | Mirror Wiki/CodeGraph provenance, ownership, and asset relationships into the graph. |
| Level 9 Orchestrator | Plan, route, checkpoint workflows | Equip each workflow agent with a scoped TencentDB memory loadout before execution. |

## Recommended architecture

```text
AGI Platform API
  ├── Memory Layer
  │   └── TencentDBMemoryConnector
  │       ├── Chat Memory adapter
  │       ├── Skill adapter
  │       ├── Wiki adapter
  │       └── CodeGraph adapter
  ├── Guardian
  │   └── Review/status/visibility policy bridge
  ├── Knowledge Graph
  │   └── Asset provenance + relationship mirror
  └── Orchestrator
      └── Agent loadout resolver
          └── TencentDB Agent Memory Proxy / Memory Hub
```

## Integration phases

### Phase 1 — Read-only memory augmentation

Goal: safely use TencentDB Agent Memory as an external context source without changing platform write paths.

1. Add configuration:
   - `TENCENTDB_MEMORY_ENABLED`
   - `TENCENTDB_MEMORY_BASE_URL`
   - `TENCENTDB_MEMORY_API_KEY`
   - `TENCENTDB_MEMORY_TEAM_ID`
   - `TENCENTDB_MEMORY_TIMEOUT_SECONDS`
2. Add `TencentDBMemoryConnector` with methods:
   - `health()`
   - `search_assets(query, agent_id, asset_types, limit)`
   - `get_asset(asset_id)`
3. Add retrieval fusion in Level 1:
   - local memory search first;
   - TencentDB external asset search second;
   - merge by score, freshness, trust, visibility, and source type.
4. Add source labels in responses:
   - `source: local_memory`
   - `source: tencentdb_chat_memory`
   - `source: tencentdb_skill`
   - `source: tencentdb_wiki`
   - `source: tencentdb_codegraph`
5. Keep writes local until review and permission mapping are proven.

### Phase 2 — Agent loadouts and permission bridge

Goal: use Memory Hub's strongest idea: memory is not global context; it is an agent-specific loadout.

1. Extend workflow request with optional `agent_id`, `team_id`, and `memory_scope`.
2. Before orchestration, call the connector to resolve assets allowed for that agent.
3. Apply platform policy:
   - `private` assets are only available to the owner;
   - `team` assets require team membership;
   - `restricted` assets require explicit ACL match;
   - `agent` assets must match the current workflow agent.
4. Record memory-loadout decisions in workflow checkpoints.
5. Expose loadout diagnostics in `/orchestrate` output for auditability.

### Phase 3 — Write-back with Guardian review

Goal: let AGI Platform contribute high-value memories back to TencentDB Agent Memory while preserving human governance.

1. Candidate memories are created as `proposed` assets.
2. Level 2 Guardian validates duplicates, sensitivity, quality, and policy compliance.
3. Human reviewers approve publishing to `team`, `restricted`, or `agent` scopes.
4. Approved assets are written to TencentDB Agent Memory through the connector.
5. Rejected assets remain local or are archived with an explanation.

### Phase 4 — CodeGraph and Wiki synchronization

Goal: connect AGI Platform repository intelligence and knowledge graph to TencentDB Wiki/CodeGraph.

1. On repository indexing, export repository metadata and symbol summaries to TencentDB CodeGraph where supported.
2. Ingest CodeGraph impact paths into Level 8 Knowledge Graph for reasoning over code relationships.
3. Convert stable platform docs and runbooks into Wiki assets.
4. Use Wiki link graph during research/report generation to reduce repeated document scanning.
5. Add drift detection when repository state and CodeGraph state diverge.

## API additions for AGI Platform

Recommended new endpoints:

- `GET /memory/external/health`
- `POST /memory/external/search`
- `POST /memory/loadout/resolve`
- `POST /memory/assets/propose`
- `POST /memory/assets/{asset_id}/approve`
- `POST /memory/assets/{asset_id}/publish`
- `POST /github/repositories/{owner}/{repo}/codegraph/sync`

## Data model additions

Recommended tables or equivalent persistent records:

- `external_memory_sources`
- `memory_assets`
- `memory_asset_versions`
- `memory_asset_bindings`
- `memory_asset_acl`
- `memory_asset_reviews`
- `memory_retrieval_events`
- `codegraph_sync_runs`

Minimum fields for `memory_assets`:

- `asset_id`
- `external_id`
- `source_system`
- `asset_type`
- `title`
- `summary`
- `owner`
- `team_id`
- `visibility`
- `status`
- `version`
- `freshness_score`
- `trust_score`
- `created_at`
- `updated_at`

## Security and governance controls

- Keep TencentDB credentials out of prompts, memory records, logs, and tool outputs.
- Default to read-only integration until approval workflows are implemented.
- Enforce least-privilege scopes per agent and per workflow.
- Log every external retrieval with query hash, agent ID, asset IDs, visibility, score, and policy decision.
- Never inject entire Wiki/CodeGraph assets into prompt context; retrieve focused snippets or impact paths on demand.
- Add timeout, item-count, character-budget, and retry limits for external retrieval.
- Treat external memory content as untrusted input and run prompt-injection checks before use.

## Success metrics

- Cold-start context assembly time reduced by at least 30% for repository and research workflows.
- Repeated context questions reduced by at least 40% across multi-session agent tasks.
- At least 95% of external memory retrievals include asset ID, version, visibility, and provenance.
- Zero high-risk write-backs occur without Guardian review and human approval.
- Code-change workflows include CodeGraph impact context for at least 80% of supported repositories.

## Immediate next implementation step

Implement a read-only `TencentDBMemoryConnector` behind configuration flags, then add a fusion layer that can return local memory results plus external memory assets with provenance. This gives immediate value while keeping the risk low because no external writes happen in the first phase.

## Implemented foundation

The first read-only foundation is now available in AGI Platform:

- `TencentDBMemoryConnector` is configurable with `TENCENTDB_MEMORY_ENABLED`, `TENCENTDB_MEMORY_BASE_URL`, `TENCENTDB_MEMORY_API_KEY`, `TENCENTDB_MEMORY_TEAM_ID`, and `TENCENTDB_MEMORY_TIMEOUT_SECONDS`.
- Local memory search now fuses local results with TencentDB Agent Memory assets when the connector is enabled.
- `GET /memory/external/health` reports whether the connector is disabled, not ready, unavailable, or healthy.
- The connector is safe-by-default: it is disabled unless explicitly enabled and does not write external memory assets.
