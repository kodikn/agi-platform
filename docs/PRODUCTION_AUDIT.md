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
