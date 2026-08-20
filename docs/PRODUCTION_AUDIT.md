# Production Audit

Audit date: 2026-08-20. Scope: all repository Python modules, API routes, tests, Dockerfile, Docker Compose, Kubernetes manifest, migrations, configuration, observability, security, sandbox, integrations, memory, graph, orchestration, governance, and self-improvement.

## Actual dependency graph

```text
api.main
  -> agi_platform.config.Settings
  -> agi_platform.security.RateLimiter/public_paths/headers
  -> agi_platform.readiness.platform_ready
  -> agi_platform.services.PlatformService
       -> LLMCore -> httpx -> external LLM providers
       -> MemoryLayer -> in-process dict
       -> MemoryGuardian -> in-process dict/list
       -> ResearchLayer -> httpx -> GitHub API when requested
       -> ChineseResearchHub -> httpx -> LibreTranslate when configured
       -> AnalysisLayer -> ast/re deterministic checks
       -> GitHubIntelligence -> httpx -> GitHub API
       -> SandboxLab -> subprocess + tempfile + POSIX resource limits
       -> KnowledgeGraph -> in-process dict/list
       -> WorkflowEngine -> JSON file state store in tempfile path
       -> ArchitectureGovernance -> in-process lists
       -> SelfImprovementEngine -> in-process list
       -> TelemetryRegistry -> in-process counters/timers
       -> ToolRegistry -> static in-process catalog
```

## Findings

| Component | Current State | Risk | Severity | Evidence | Required Fix | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Readiness | `/ready` reports platform status from module imports and catalog declarations, not real critical controls. | False GREEN can send traffic to a non-production runtime. | CRITICAL | `agi_platform/readiness.py` used static import/API/schema/metrics/security criteria. | Gate readiness with production controls and dependency/capability checks; report RED/YELLOW/GREEN honestly. | Config, health checks, dependency clients. | `/ready` is not GREEN while durable state, authz, sandbox isolation, and dependency checks are absent. |
| Memory | Canonical memory state is an in-process dict. | Process restart loses memories; no tenant isolation, provenance, retention, or concurrency control. | CRITICAL | `MemoryLayer.records` in `agi_platform/memory/core.py`. | Persist metadata in Postgres, vectors in Qdrant, provenance/evidence and tenant constraints. | Postgres, Qdrant, migrations. | Restart preserves memory; cross-tenant tests pass; memory has provenance/confidence/version. |
| Memory Guardian | Versions, reviews, and audit are in-process containers. | Rollback/audit are not durable or immutable. | HIGH | `MemoryGuardian.versions`, `audit`, `reviews` in `agi_platform/guardian/core.py`. | Append immutable audit events and version rows transactionally. | Event store, Postgres. | Rollback and reviews survive restart and emit events. |
| Orchestration | Workflow state is JSON-file backed with in-memory run list. | Not safe for multi-worker concurrency; missing idempotency, locks, dead-letter, retry policies. | HIGH | `WorkflowStateStore` writes a JSON file; `WorkflowEngine.runs` remains process memory. | Store runs, tasks, checkpoints, and events transactionally with optimistic concurrency/idempotency. | Domain model, event store, Postgres/Redis locks. | Crash/restart resumes without duplicate non-idempotent side effects. |
| Sandbox | Subprocess execution now has scrubbed env and POSIX resource limits but not a hard isolation boundary. | Untrusted code can still access host kernel/network namespace capabilities depending on runtime. | CRITICAL | `SandboxLab.execute()` uses `subprocess.run` in `agi_platform/sandbox/core.py`. | Move execution into non-root container/microVM with read-only rootfs, network policy, disk quota, artifact extraction, and escape tests. | Container runtime or microVM, policy engine. | Sandbox escape/resource/secret/network tests pass against isolated runtime. |
| API Authn/Authz | Optional API key only; no actor/tenant identity or tool/resource authorization. | Any authenticated key can call high-risk endpoints. | CRITICAL | `api/main.py` checks only `X-API-Key` when configured. | Add identity, tenant context, RBAC/ABAC/capability checks per endpoint/tool. | Domain model, policy engine, audit events. | Protected endpoints require scoped permissions; high-risk operations require approval. |
| Error handling | Routes catch broad `Exception` and return provider error strings. | Internal/provider details may leak and errors are not normalized. | HIGH | Broad catches in `/chat`, `/completion`, `/embeddings`, `/github/repositories`. | Canonical exception hierarchy and sanitized error model with request_id. | API middleware, logging. | No stack traces/secrets/internal paths in production responses. |
| LLM Core | Real HTTP calls with timeout, but no retry/circuit-breaker/provider health/policy-aware fallback. | Provider outage or rate limits cause fragile behavior and unbounded cost policy gaps. | HIGH | `LLMCore.complete()` and `embeddings()` call providers directly. | Add provider adapters, health, retry budget, circuit breaker, usage/cost persistence, policy-aware routing. | Config, telemetry, persistence. | Retryable failures handled; non-retryable failures not retried; cost/token metrics persisted. |
| Research | Uses httpx timeouts and evidence list but no SSRF, size, content-type, redirect, or source policy controls. | SSRF/resource exhaustion/untrusted content risk. | HIGH | `ResearchLayer.query()`/`_collect_source()` in `agi_platform/research/core.py`. | Add URL policy, response limit, content-type validation, redirect policy, evidence persistence. | Policy engine, evidence model. | SSRF tests for metadata/private IP/file URLs fail closed. |
| GitHub Intelligence | Fetches repo and first contributors page only; stores in-process. | Large repos/rate limits/pagination not handled; state lost on restart. | MEDIUM | `GitHubIntelligence.repositories` dict and two GitHub requests. | Incremental indexing with pagination, rate-limit handling, content hashing, checkpoints. | Postgres, event store. | Reindex resumes after failure and records GitHub rate-limit telemetry. |
| Knowledge Graph | In-process nodes/edges. | No Neo4j durability, tenant isolation, constraints, traversal limits. | HIGH | `KnowledgeGraph.nodes` and `edges`. | Add Neo4j schema/constraints, query limits, relationship provenance. | Neo4j, migrations/provisioning. | Graph survives restart; unrestricted traversal rejected. |
| Governance | Decisions/reviews are in-process and low-risk proposals auto-approve. | Approval trail is mutable/lost; high-risk gates not globally enforced. | HIGH | `ArchitectureGovernance.decisions/reviews`. | Persistent ADR records, scoped/time-bound approvals, policy enforcement for dangerous actions. | Event store, policy engine. | HIGH/CRITICAL actions blocked until explicit approval. |
| Self Improvement | Produces proposals only; no deployment mutation path, but no formal lifecycle. | Future self-modification could bypass gates without a defined model. | MEDIUM | `SelfImprovementEngine.evaluate()`. | Proposal -> benchmark -> risk -> approval -> sandbox -> canary -> deploy -> rollback lifecycle. | Governance, sandbox, CI. | Self-improvement cannot mutate production without approval event. |
| Docker | Single-stage image runs as default user. | Larger attack surface and root runtime risk. | HIGH | `Dockerfile` uses `python:3.12-slim`, no USER. | Multi-stage build, non-root user, pinned image digest/version, healthcheck/SBOM. | Build tooling. | Container runs non-root and passes vulnerability/secret scans. |
| Kubernetes | Deployment/service only; no NetworkPolicy, HPA, PDB, ServiceAccount/RBAC. | Insufficient blast-radius and availability controls. | MEDIUM | `k8s/api.yaml` contains Deployment and Service only. | Add NetworkPolicy, PDB, HPA, ServiceAccount, RBAC, read-only fs where possible. | Cluster policies. | Deployment validation passes and pod has restricted permissions. |
| Migrations | One SQL file with basic tables; many advertised tables absent and constraints/indexes are minimal. | Data model cannot enforce ownership, state machines, tenant isolation, or audit immutability. | HIGH | `migrations/001_platform_schema.sql`. | Versioned Alembic migrations or equivalent with FK/check/unique/index constraints. | Postgres. | Fresh install and upgrade tests validate schema constraints. |
| Observability | In-process Prometheus text metrics; no request/correlation IDs or structured logs. | Debugging distributed failures is difficult; metrics lost on restart. | MEDIUM | `TelemetryRegistry` and middleware lack correlation propagation. | Add JSON logs, request IDs, trace context, workflow/task/agent IDs in events/metrics. | Middleware, event model. | Every request/operation has request_id/correlation_id in logs and metrics labels where safe. |

## Implementation plan

1. Stop false GREEN readiness and add explicit production controls matrix.
2. Add canonical domain objects, lifecycle state machines, and immutable event shape.
3. Move orchestration/events to durable transactional storage with idempotency and recovery tests.
4. Add policy engine and scoped authorization for tools/agents/high-risk endpoints.
5. Replace subprocess sandbox with container/microVM isolation and security tests.
6. Add persistent memory/evidence/graph ownership and migrations.
7. Harden external integrations with SSRF controls, retries, circuit breakers, and telemetry.
8. Complete Docker/Kubernetes/CI/security gates and production certification.

## 2026-08-20 Phase 1 security foundation delta

Implemented in this change set:

- Added a tenant-aware API key record parser for `AGI_API_KEYS` JSON credentials and retained `AGI_API_KEY` only as a legacy full-access compatibility key.
- Added explicit route-to-permission mapping for protected API operations, including high-risk sandbox, GitHub, graph, orchestration, governance, and evolution endpoints.
- Added request-scoped identity and tenant context from `X-API-Key` and `X-Tenant-ID`; mismatched tenant headers fail closed.
- Added canonical API errors shaped as `error.code`, `error.message`, and `error.request_id`; 5xx handlers return sanitized messages rather than raw exception text.
- Added an outbound URL policy primitive that allows only HTTP/HTTPS and denies loopback, RFC1918, link-local, metadata, reserved, and unsafe schemes after DNS resolution.

Still not production-ready:

- Identity, tenants, roles, permissions, and API keys are not yet backed by Postgres migrations or rotation/audit workflows.
- Authorization decisions are route-scoped but not yet resource-level ABAC with durable policy events.
- SSRF policy is implemented as a reusable control and regression-tested, but all external integrations still need to adopt redirect-by-redirect streaming enforcement.
- Rate limiting remains in-process and must move to Redis or edge enforcement for multi-replica deployments.

## 2026-08-20 Tenant isolation delta

Phase 0 verification of current HEAD confirmed that tenant-scoped API keys, route permissions, canonical errors, SSRF policy primitives, readiness controls, the domain kernel, control-plane schema, JSON-backed workflow state, subprocess sandbox hardening, credential-parameterized Compose config, and production documentation exist, but most controls remain PARTIAL rather than production-complete.

Internal readiness classification after the audit:

| Priority | Control | Status | Evidence summary |
| --- | --- | --- | --- |
| P0 | Authn/authz route permissions | PARTIAL | Scoped keys and route permissions exist; durable identity storage, rotation, and audit are still missing. |
| P0 | Tenant isolation | PARTIAL | API now propagates tenant context into memory, workflow, graph, and sandbox results; Postgres/Qdrant/Neo4j/RLS enforcement is still missing. |
| P0 | Workflow durability | PARTIAL | JSON checkpoint persistence and tenant/idempotency scoping exist; transactional Postgres state, leases, locks, retries, and dead-letter recovery remain missing. |
| P0 | Sandbox hard isolation | NOT DONE | Runtime still uses subprocess/POSIX limits rather than a container or microVM boundary. |
| P0 | Secrets/config | PARTIAL | No hardcoded production API keys were added; production fail-fast weak secret validation is still missing. |
| P0 | Database integrity | PARTIAL | Initial SQL schema exists; complete tenant-owned FK/check/index/version coverage and upgrade/rollback tests remain missing. |
| P1 | Persistent memory | NOT DONE | Memory is tenant-filtered but still process-local and not persisted to Postgres/Qdrant. |
| P1 | Persistent graph | NOT DONE | Graph is tenant-filtered but still process-local and not persisted to Neo4j. |
| P1 | LLM resilience | NOT DONE | Provider calls use timeouts but no retry budget, circuit breaker, quotas, or durable usage/cost persistence. |
| P1 | Distributed rate limiting | NOT DONE | Rate limiting remains in-process. |
| P1 | Observability | PARTIAL | Metrics exist; OpenTelemetry traces and structured logs are missing. |
| P1 | Kubernetes/Docker/CI/backup/load/chaos/governance | PARTIAL | Manifests/docs/tests exist only in partial form and require production-grade implementation. |

Implemented in this tenant-isolation increment:

- Memory records now include `tenant_id`, tenant-scoped identifiers, content hash, status, timestamps, and version metadata; search and consolidation filter by tenant.
- Workflow plans now include `tenant_id` and optional idempotency key; checkpoint lookup, execute, and recover require the matching tenant.
- Knowledge graph nodes and relationships now carry `tenant_id`; entity keys, relationship creation, and search are tenant-scoped with a max result cap.
- Sandbox execution results now include `tenant_id`, preserving artifact/result ownership for future durable artifact APIs.
- Added negative tenant-isolation tests for memory read/update-equivalence, workflow recovery, graph search, and sandbox artifact/result ownership.
