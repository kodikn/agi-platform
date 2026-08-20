# Production Gap Analysis

Audit date: 2026-08-20. Scope: `agi_platform/`, `api/`, `tests/`, `migrations/`, `Dockerfile`, `docker-compose.yml`, `k8s/`, CI/CD, docs, configuration, integrations, memory, graph, orchestration, sandbox, governance, self-improvement, and observability.

This document is an audit artifact only. It does not change production behavior. The repository must not be described as production-ready while any P0 blocker remains open. Passing unit tests is insufficient evidence of production readiness; production readiness requires persistence/recovery, tenant-isolation, authorization, sandbox, security, failure-injection, backup/restore, and deployment tests.

## Severity model

- **P0**: Blocks production because it can cause data loss, cross-tenant access, remote code execution, sandbox escape, false readiness, severe security exposure, or unrecoverable operations.
- **P1**: High-impact reliability, security, compliance, or operability gap that must be fixed before broad production traffic.
- **P2**: Important hardening, scale, maintainability, or quality improvement.

## Findings

### GAP-001: Critical domain state is process-local

| Field | Detail |
| --- | --- |
| Component | Memory, guardian, graph, governance, evolution, telemetry, service composition |
| File | `agi_platform/services.py`, `agi_platform/memory/core.py`, `agi_platform/guardian/core.py`, `agi_platform/knowledge_graph/core.py`, `agi_platform/governance/core.py`, `agi_platform/evolution/core.py`, `agi_platform/telemetry.py` |
| Current behavior | `PlatformService` constructs all core services in process; memory records, memory reviews/audit/versions, graph nodes/edges, governance decisions/reviews, self-improvement evaluations, and metrics live in Python dictionaries/lists. |
| Risk | Restart, deploy, pod eviction, or multi-replica routing loses state and audit history; replicas diverge; compliance and recovery claims cannot be proven. |
| Severity | P0 |
| Root cause | Runtime implementations are prototype adapters and do not use the declared Postgres/Qdrant/Neo4j/Redis dependencies. |
| Recommended implementation | Introduce repository interfaces and transactional Postgres persistence for metadata/events/audit; Qdrant for vectors; Neo4j for graph; Redis or Postgres-backed counters/rate-limits where needed. Wire services through dependency-injected persistent stores instead of process-local containers. |
| Dependencies | Postgres migrations, Qdrant collections, Neo4j constraints, Redis, repository layer, transaction boundaries, migration runner. |
| Tests | Restart persistence tests, two-replica consistency tests, tenant-scoped data access tests, crash-during-write tests, audit immutability tests. |
| Acceptance criteria | Data written by one process survives restart and is visible to authorized requests in another process; audit/event history is immutable; no critical domain state relies on process memory. |

### GAP-002: Workflow persistence uses a shared JSON file without concurrency control

| Field | Detail |
| --- | --- |
| Component | Orchestration and recovery |
| File | `agi_platform/orchestration.py` |
| Current behavior | Workflow checkpoints are stored in a JSON file under a temp directory by default; writes read the full list, replace matching checkpoint, and rewrite the file. `WorkflowEngine.runs` is still in memory. |
| Risk | Concurrent workers can lose updates, corrupt workflow state, duplicate executions, or overwrite checkpoints. Temp storage can be erased by container restart or node cleanup. |
| Severity | P0 |
| Root cause | File-backed prototype store with no locking, optimistic versioning, idempotency enforcement, durable event sequence, or transactional task state. |
| Recommended implementation | Move workflow runs, task runs, checkpoints, and events into Postgres with optimistic concurrency (`version`), unique idempotency keys, event sequence constraints, row-level locks, and dead-letter/retry tables. |
| Dependencies | Postgres repository, migration runner, idempotency middleware, durable event bus/outbox, worker coordination. |
| Tests | Parallel execute/recover tests, double-submit idempotency tests, crash-after-step tests, corrupted checkpoint recovery tests, multi-replica workflow tests. |
| Acceptance criteria | Concurrent execution cannot duplicate non-idempotent work; recovery replays from durable events/checkpoints; temp filesystem loss does not lose workflows. |

### GAP-003: Tenant context is authenticated but not applied to domain data

| Field | Detail |
| --- | --- |
| Component | API, memory, graph, workflow, governance, GitHub intelligence, research, telemetry |
| File | `api/main.py`, `agi_platform/security.py`, `agi_platform/memory/core.py`, `agi_platform/knowledge_graph/core.py`, `agi_platform/orchestration.py`, `agi_platform/governance/core.py`, `agi_platform/github_intel/core.py` |
| Current behavior | Middleware stores `request.state.tenant_id`, but route handlers do not pass tenant identity into service calls. Stored records do not include tenant IDs and searches are global. |
| Risk | Authenticated users from one tenant can read or mutate data created by another tenant when using shared process state. This is a production-stopping isolation failure. |
| Severity | P0 |
| Root cause | Tenant identity exists only in middleware state; service APIs and domain records are not tenant-scoped. |
| Recommended implementation | Require a request context object for every service mutation/query. Add `tenant_id`, `actor_id`, and authorization decision metadata to all persistent records and query predicates. Enforce row-level tenant filters and database constraints. |
| Dependencies | Request context model, persistent tenant tables, repository layer, ABAC/policy engine, tests using separate tenants. |
| Tests | Cross-tenant memory/graph/workflow/governance read/write denial tests, tenant mismatch tests, persistence-level row filter tests, admin break-glass audit tests. |
| Acceptance criteria | No tenant can observe or mutate another tenant's state without an explicit audited cross-tenant capability. |

### GAP-004: Authorization is route-scoped, not resource- or capability-scoped

| Field | Detail |
| --- | --- |
| Component | Authentication and authorization |
| File | `agi_platform/security.py`, `api/main.py`, `agi_platform/tool_registry.py` |
| Current behavior | API keys map to static permission strings and routes. No authorization decision includes resource ownership, risk, tool contract, approval scope, budget, or workflow context. Legacy `AGI_API_KEY` grants `*`. |
| Risk | A key with a route permission can act on any resource handled by that route. Tool execution, graph mutation, governance review, and workflow execution lack contextual least privilege. |
| Severity | P0 |
| Root cause | Static route-to-permission map and no policy decision point/policy enforcement point separation. |
| Recommended implementation | Add a policy engine that evaluates actor, tenant, resource, action, risk level, approval, tool contract, and request context. Replace legacy full-access keys with rotated, hashed, scoped credentials stored durably. |
| Dependencies | Identity store, key hashing/rotation, policy engine, approval records, audit events, resource ownership model. |
| Tests | Resource-level denial tests, high-risk approval tests, expired approval tests, legacy-key disablement tests, policy event audit tests. |
| Acceptance criteria | Authorization decisions are deny-by-default, resource-scoped, auditable, and enforce high-risk approval gates. |

### GAP-005: Sandbox is subprocess-based and not a security boundary

| Field | Detail |
| --- | --- |
| Component | Sandbox/RCE containment |
| File | `agi_platform/sandbox/core.py`, `api/main.py`, `Dockerfile`, `k8s/api.yaml` |
| Current behavior | `/sandbox/execute` runs allowed commands via `subprocess.run` with scrubbed environment, temp working directory, POSIX resource limits, and an allowlist of command names. |
| Risk | Untrusted code still runs inside the API container/pod security context and host kernel namespace. Python code can inspect process/container resources, attempt syscalls, fork within limits, abuse interpreter behavior, or exploit kernel/runtime vulnerabilities. |
| Severity | P0 |
| Root cause | The sandbox relies on process limits rather than a separate container, microVM, gVisor/Kata/Firecracker boundary, seccomp/apparmor profile, network namespace, and read-only filesystem. |
| Recommended implementation | Move execution to an isolated non-root worker sandbox with no secrets, read-only rootfs, network disabled by default, per-run cgroups, seccomp/AppArmor, disk quota, artifact extraction, and short-lived disposable runtime. |
| Dependencies | Container/microVM runtime, sandbox scheduler, artifact store, policy engine, escape test harness, per-run audit events. |
| Tests | Escape tests, secret exfiltration tests, network-denial tests, filesystem write tests, fork bomb tests, CPU/memory/disk quota tests, artifact cleanup tests. |
| Acceptance criteria | Host/API secrets and filesystem are inaccessible from sandboxed code; network and filesystem policies are enforced by runtime isolation, not application convention. |

### GAP-006: External HTTP integrations do not consistently apply SSRF and response controls

| Field | Detail |
| --- | --- |
| Component | Research, GitHub intelligence, Chinese translation, LLM providers |
| File | `agi_platform/security.py`, `agi_platform/research/core.py`, `agi_platform/github_intel/core.py`, `agi_platform/chinese_hub/core.py`, `agi_platform/llm/core.py` |
| Current behavior | A reusable `validate_outbound_url` helper exists, but integration code performs direct `httpx` requests. GitHub URLs are host-limited; LibreTranslate endpoint and provider base URLs are environment-controlled and not validated per redirect. Response size/content type is not bounded. |
| Risk | SSRF, metadata-service access through misconfigured endpoints, redirect-to-private-network attacks, memory exhaustion, and untrusted content ingestion. |
| Severity | P0 |
| Root cause | URL policy is not enforced centrally by an outbound HTTP client wrapper; no streaming response limits or redirect-by-redirect validation. |
| Recommended implementation | Create a hardened outbound client that validates scheme/host/DNS on every request and redirect, disables or constrains redirects, enforces max response bytes, content-type allowlists, timeouts, and source policy. Use it for all integrations. |
| Dependencies | Outbound policy module, integration adapters, DNS pinning/re-resolution strategy, telemetry, SSRF regression suite. |
| Tests | Metadata IP tests, RFC1918/loopback/IPv6/link-local tests, DNS rebinding tests, redirect-to-private tests, oversized response tests, disallowed content-type tests. |
| Acceptance criteria | All outbound traffic goes through one policy-enforcing client and fails closed for unsafe destinations and responses. |

### GAP-007: LLM provider reliability and cost controls are incomplete

| Field | Detail |
| --- | --- |
| Component | LLM Core |
| File | `agi_platform/llm/core.py`, `agi_platform/services.py`, `migrations/001_platform_schema.sql` |
| Current behavior | Provider calls use a fixed timeout and direct `httpx` POST. Usage is appended to an in-memory list; cost is always `0.0`. No retry budget, circuit breaker, provider health, fallback policy, quota, or durable cost accounting exists. |
| Risk | Provider outages cause fragile user-facing failures; retries added later could duplicate costs without idempotency; uncontrolled usage can create runaway spend; usage records disappear on restart. |
| Severity | P1 |
| Root cause | Provider adapter layer and durable usage/cost ledger are not implemented. |
| Recommended implementation | Add provider adapters with retry classification, circuit breakers, fallback routing, per-tenant budgets, model allowlists, token/cost estimation, durable usage ledger, and alerting. |
| Dependencies | Durable usage/cost schema, policy engine, telemetry, provider health probes, budget configuration. |
| Tests | Provider timeout/rate-limit/failure injection tests, budget-exceeded tests, fallback tests, duplicate billing/idempotency tests. |
| Acceptance criteria | Retryable failures are retried within budget; non-retryable failures are not retried; cost and token records persist per tenant and model. |

### GAP-008: Readiness remains largely declared rather than proven by live dependency checks

| Field | Detail |
| --- | --- |
| Component | Readiness and deployment gating |
| File | `agi_platform/readiness.py`, `api/main.py`, `k8s/api.yaml`, `docs/production.md` |
| Current behavior | `/ready` reports not-ready/degraded based on module imports and hard-coded control assessments. It does not run live checks against Postgres, Redis, Qdrant, Neo4j, provider dependencies, migrations, or sandbox isolation capability. |
| Risk | Readiness can drift from actual runtime health and either block safe traffic unnecessarily or, after assessments are edited, produce false positives without proving data-path capability. |
| Severity | P1 |
| Root cause | No dependency clients, migration version checks, or capability probes are wired into readiness. |
| Recommended implementation | Add bounded live probes for database connectivity/migration version, Redis rate-limit backend, Neo4j constraints, Qdrant collection health, outbound provider health, and isolated sandbox runtime. Keep `/live` lightweight. |
| Dependencies | Dependency clients, migration runner, health check budgets/timeouts, Kubernetes probe policy. |
| Tests | Dependency-down tests, stale migration tests, sandbox runtime unavailable tests, slow dependency timeout tests. |
| Acceptance criteria | `/ready` is green only when critical dependencies and capabilities are demonstrably operational. |

### GAP-009: Migration strategy is not production-grade

| Field | Detail |
| --- | --- |
| Component | Database migrations and schema ownership |
| File | `migrations/001_platform_schema.sql`, `tests/test_migrations.py`, `docs/PRODUCTION_DEFINITION_OF_DONE.md` |
| Current behavior | A single SQL file declares prototype tables and newer control-plane tables. There is no migration tool metadata, ordering, rollback plan, online migration strategy, seed/fixture strategy, or verification against a live database in CI. |
| Risk | Fresh installs and upgrades can diverge; destructive/locking changes cannot be managed; backup/restore compatibility is untested; schema can exist without code using it. |
| Severity | P1 |
| Root cause | Migration declaration is not integrated with runtime, CI, or deployment lifecycle. |
| Recommended implementation | Adopt Alembic or equivalent versioned migrations; run migrations in CI and deploy; add schema drift checks, downgrade/rollback policy, online migration conventions, seed data, and constraint validation. |
| Dependencies | Migration tooling, test Postgres service in CI, deployment job, backup/restore procedure. |
| Tests | Fresh database migration test, upgrade-from-previous-version test, rollback/downgrade test where supported, schema drift test, restore-from-backup test. |
| Acceptance criteria | Every release has repeatable, ordered, verified migrations and documented rollback/restore behavior. |

### GAP-010: Backup and restore are absent

| Field | Detail |
| --- | --- |
| Component | Persistence, operations, disaster recovery |
| File | `docker-compose.yml`, `k8s/api.yaml`, `docs/deployment.md`, `docs/production.md` |
| Current behavior | Compose starts stateful services but does not declare durable volumes or backup jobs. Kubernetes manifests only include API Deployment/Service; no database, backup CronJob, restore runbook, or disaster recovery test exists. |
| Risk | Data loss after container removal, node failure, operator error, or corrupted migration; recovery point objective/recovery time objective are undefined. |
| Severity | P0 |
| Root cause | Operational persistence and DR design are not represented in manifests, docs, or tests. |
| Recommended implementation | Define managed database/storage expectations, persistent volumes for local compose, backup schedules, encrypted offsite backups, restore drills, RPO/RTO, and migration-aware restore validation. |
| Dependencies | Managed Postgres/Qdrant/Neo4j/Redis or persistent volumes, backup tooling, secret manager, runbooks. |
| Tests | Backup creation test, restore into clean environment, point-in-time recovery test, corrupted backup detection test, DR drill in staging. |
| Acceptance criteria | A clean environment can be restored from backup and pass consistency/integrity checks within stated RPO/RTO. |

### GAP-011: Docker image runs as root and is not hardened

| Field | Detail |
| --- | --- |
| Component | Docker runtime security |
| File | `Dockerfile` |
| Current behavior | Single-stage `python:3.12-slim` image installs dependencies and runs Uvicorn as the default image user. No pinned digest, non-root user, healthcheck, SBOM, vulnerability scan, or minimal runtime stage exists. |
| Risk | Container compromise has root privileges inside the container; supply chain and vulnerability posture are not controlled; image is larger than necessary. |
| Severity | P1 |
| Root cause | Development-oriented Dockerfile. |
| Recommended implementation | Use pinned digest or controlled base image, multi-stage build, non-root user, minimal runtime files, Docker HEALTHCHECK, pip hash checking or lockfile, SBOM generation, vulnerability and secret scans. |
| Dependencies | Build pipeline, lockfile generation, scanner tooling, base image update policy. |
| Tests | Container starts as non-root, image vulnerability threshold, SBOM presence, secret scan, healthcheck validation. |
| Acceptance criteria | Runtime image is non-root, reproducible, scanned, and contains only required artifacts. |

### GAP-012: Kubernetes manifest lacks production security and availability controls

| Field | Detail |
| --- | --- |
| Component | Kubernetes deployment |
| File | `k8s/api.yaml` |
| Current behavior | Deployment and Service exist with probes, resources, seccomp, dropped capabilities, and `allowPrivilegeEscalation: false`; `readOnlyRootFilesystem` is false. There is no ServiceAccount/RBAC, NetworkPolicy, PodDisruptionBudget, HPA, topology spread, ingress/TLS policy, secret rotation, or egress policy. |
| Risk | Excessive network blast radius, weaker availability during disruption, no autoscaling, no explicit pod identity boundaries, and writable filesystem in compromised pod. |
| Severity | P1 |
| Root cause | Minimal API manifest rather than full production platform chart/kustomize/helm deployment. |
| Recommended implementation | Add restricted ServiceAccount/RBAC, NetworkPolicies for ingress/egress, PDB, HPA/KEDA, read-only root filesystem with writable tmp volume, topology spread, pod anti-affinity, ingress TLS/WAF policy, and external secret integration. |
| Dependencies | Cluster policy standards, ingress controller, external secrets, metrics server, autoscaler. |
| Tests | Policy conformance tests, kube-score/kube-linter, network egress deny tests, disruption/autoscale tests. |
| Acceptance criteria | API pods run with least privilege, controlled network paths, disruption budget, autoscaling policy, and read-only root filesystem. |

### GAP-013: CI/CD validates only basic unit tests

| Field | Detail |
| --- | --- |
| Component | CI/CD and release gates |
| File | `.github/workflows/ci.yml` |
| Current behavior | CI checks out code, installs Python 3.12 dependencies, and runs `pytest`. It does not run linting, type checking, dependency audit, SAST, container build/scan, migration test against live Postgres, integration tests, failure injection, or Kubernetes validation. |
| Risk | Security, packaging, deployment, migration, and runtime failure modes can merge undetected. Passing `pytest` can be mistaken for production readiness. |
| Severity | P1 |
| Root cause | Minimal CI workflow. |
| Recommended implementation | Add jobs for formatting/lint/type checks, dependency vulnerabilities, secrets scanning, migration tests with service containers, Docker build/SBOM/scan, Kubernetes manifest validation, integration tests, and failure-injection suites. |
| Dependencies | CI service containers, scanners, linters, build cache, test secrets policy. |
| Tests | CI itself should exercise migration, integration, container, and k8s validation paths. |
| Acceptance criteria | A PR cannot merge unless code, dependencies, migrations, image, manifests, and security checks pass required gates. |

### GAP-014: Rate limiting is process-local and weak for multi-replica deployments

| Field | Detail |
| --- | --- |
| Component | API rate limiting and abuse prevention |
| File | `agi_platform/security.py`, `api/main.py`, `agi_platform/config.py` |
| Current behavior | `RateLimiter` stores request timestamps in an in-memory dictionary keyed by API key or client host. There is no Redis/edge limiter, per-tenant budget, request body size limit, concurrency limit, or backpressure. |
| Risk | Limits reset on restart, differ per replica, can be bypassed through load balancing, and do not protect expensive LLM/sandbox operations from concurrency spikes. |
| Severity | P1 |
| Root cause | Prototype in-process limiter. |
| Recommended implementation | Move rate limits and quotas to Redis or API gateway/edge; add per-tenant/model/tool budgets, concurrency semaphores, request body size limits, and abuse metrics. |
| Dependencies | Redis, gateway/ingress config, policy engine, telemetry alerts. |
| Tests | Multi-replica rate-limit tests, burst tests, body-size tests, concurrent sandbox/LLM limit tests. |
| Acceptance criteria | Rate limits and quotas are enforced consistently across replicas and survive restarts. |

### GAP-015: Governance approvals are mutable and not globally enforced

| Field | Detail |
| --- | --- |
| Component | Governance and approvals |
| File | `agi_platform/governance/core.py`, `api/main.py`, `agi_platform/evolution/core.py`, `agi_platform/sandbox/core.py` |
| Current behavior | Low-risk proposals auto-approve; decisions and reviews are mutable list items; high-risk operations in sandbox/workflow/evolution are not linked to durable approval records. |
| Risk | Approval bypass, repudiation, lost review history, and unsafe future self-improvement or sandbox operations without human authorization. |
| Severity | P0 |
| Root cause | Governance is advisory and in-memory; policy enforcement does not consult approval state. |
| Recommended implementation | Persist approvals as immutable, scoped, expiring records; require approvals for high/critical tool execution and self-improvement lifecycle transitions; enforce in middleware/service policy. |
| Dependencies | Policy engine, durable event/audit store, identity store, approval UI/process. |
| Tests | High-risk action denied without approval, approval scope mismatch tests, expired approval tests, immutable audit tests. |
| Acceptance criteria | High/critical actions cannot execute without valid durable approval and auditable policy decision. |

### GAP-016: Self-improvement lifecycle has no deployment safety model

| Field | Detail |
| --- | --- |
| Component | Self-improvement |
| File | `agi_platform/evolution/core.py`, `docs/SECURITY_ARCHITECTURE.md`, `docs/PRODUCTION_DEFINITION_OF_DONE.md` |
| Current behavior | The engine produces improvement proposals and stores evaluations in memory. There is no mutation path now, but there is also no enforced proposal-to-benchmark-to-approval-to-canary-to-rollback lifecycle. |
| Risk | Future self-modifying behavior could be added without guardrails, allowing unreviewed changes to production systems. |
| Severity | P1 |
| Root cause | No formal policy/state machine for self-improvement beyond proposal generation. |
| Recommended implementation | Define immutable lifecycle states, benchmark gates, risk scoring, human approval, isolated validation, canary deployment, rollback criteria, and audit events before any mutation capability is added. |
| Dependencies | Governance, CI/CD, sandbox, deployment controller, metrics. |
| Tests | Mutation blocked tests, benchmark failure tests, canary rollback tests, approval-required tests. |
| Acceptance criteria | Self-improvement cannot alter production without passing durable, audited gates. |

### GAP-017: Observability is not sufficient for production incident response

| Field | Detail |
| --- | --- |
| Component | Metrics, logs, traces, auditability |
| File | `agi_platform/telemetry.py`, `api/main.py`, `monitoring/prometheus.yml` |
| Current behavior | Metrics are in-process counters/histograms rendered as Prometheus text. Request IDs are returned in headers, but there is no structured logging, distributed tracing, persistent audit/event stream, SLOs, alerts, or safe high-cardinality label policy. |
| Risk | Incidents cannot be correlated across API, workflows, providers, sandbox, and storage. Metrics disappear on restart and do not support multi-replica aggregation beyond scraping current process state. |
| Severity | P1 |
| Root cause | Minimal telemetry registry and Prometheus scrape config. |
| Recommended implementation | Add structured JSON logs with request/correlation/workflow/task IDs, OpenTelemetry traces, durable audit/event stream, RED/USE metrics, SLO dashboards, alerts, and trace propagation to outbound calls. |
| Dependencies | Logging configuration, OTEL collector, Prometheus/Alertmanager/Grafana, event store. |
| Tests | Log redaction tests, trace propagation tests, metrics label tests, alert rule tests. |
| Acceptance criteria | Every mutation and provider/tool call is traceable from request to audit/event record with redacted logs and actionable alerts. |

### GAP-018: Secret handling and leakage controls are incomplete

| Field | Detail |
| --- | --- |
| Component | Secrets, integrations, errors, CI/CD |
| File | `agi_platform/config.py`, `agi_platform/llm/core.py`, `agi_platform/research/core.py`, `agi_platform/github_intel/core.py`, `agi_platform/chinese_hub/core.py`, `.github/workflows/ci.yml` |
| Current behavior | Secrets are read from environment variables and passed to providers. There is no central secret manager abstraction, key rotation, redaction filter, secret scan in CI, or explicit prevention of secrets entering LLM prompts/tool output/sandbox logs. |
| Risk | Secrets can leak through logs, provider payloads, sandbox output, raw provider responses, repo analysis, or CI artifacts. |
| Severity | P1 |
| Root cause | Secret management is environment-variable based and not integrated with redaction, policy, or scanning. |
| Recommended implementation | Use external secret manager/Kubernetes External Secrets, redact secrets in logs/errors/metrics, scan code and artifacts, prevent secrets from being passed to sandbox/LLM context, and rotate API/provider keys. |
| Dependencies | Secret manager, redaction library, CI scanners, policy engine. |
| Tests | Secret redaction tests, sandbox secret absence tests, LLM prompt secret prevention tests, CI secret scanning. |
| Acceptance criteria | Secrets are centrally managed, rotated, never logged, never exposed to sandbox, and detected by CI if committed. |

### GAP-019: GitHub indexing lacks pagination, checkpointing, and secret/content policy

| Field | Detail |
| --- | --- |
| Component | GitHub intelligence |
| File | `agi_platform/github_intel/core.py` |
| Current behavior | Indexing fetches repo metadata and a single contributors page, then stores a record in memory. Repository URL validation is limited to GitHub host and path shape. |
| Risk | Large repositories, rate limits, pagination, API failures, and partial indexing are not handled. Retrieved content could later include secrets or untrusted data without policy. |
| Severity | P2 |
| Root cause | Prototype synchronous indexing with no durable checkpoints or source policy. |
| Recommended implementation | Add durable repository index jobs, pagination, ETag/content hashes, rate-limit handling, incremental checkpoints, secret scanning, and source trust policy. |
| Dependencies | Job queue, Postgres repository tables, GitHub API adapter, secret scanner, telemetry. |
| Tests | Pagination tests, rate-limit tests, resume-after-failure tests, secret detection tests. |
| Acceptance criteria | Indexing resumes safely, respects GitHub rate limits, and records durable provenance/content hashes. |

### GAP-020: Analysis findings lack durable lifecycle and comprehensive detection

| Field | Detail |
| --- | --- |
| Component | Static/repository analysis |
| File | `agi_platform/analysis/core.py` |
| Current behavior | Analysis uses a few AST/regex checks and stores run results in memory. Findings do not have stable fingerprints, lifecycle status, ownership, suppression workflow, or persistence. |
| Risk | Findings disappear, duplicate, cannot be triaged over time, and create false confidence because coverage is shallow. |
| Severity | P2 |
| Root cause | Demonstration analyzer rather than integrated SAST/dependency scanner. |
| Recommended implementation | Add finding fingerprints, status lifecycle, durable storage, SARIF export, dependency/SBOM scanning, configurable rule packs, and triage workflow. |
| Dependencies | Persistent findings schema, scanners, SARIF tooling, governance workflow. |
| Tests | Fingerprint stability tests, suppression tests, SARIF validation, scanner integration tests. |
| Acceptance criteria | Findings are durable, deduplicated, triageable, and generated by validated scanners/rules. |

### GAP-021: Docker Compose is development-oriented and exposes stateful services publicly

| Field | Detail |
| --- | --- |
| Component | Local deployment and stateful services |
| File | `docker-compose.yml`, `README.md` |
| Current behavior | Compose exposes Postgres, Qdrant, Redis, and Neo4j ports on the host and uses default local passwords. No named volumes are declared for persistent data. |
| Risk | Accidental use outside a private development machine can expose databases; container recreation can lose data; default credentials increase compromise risk. |
| Severity | P1 |
| Root cause | Compose file is optimized for local development, not production-like operations. |
| Recommended implementation | Mark compose as development-only, add named volumes for local durability, bind stateful services to localhost, require non-default secrets for non-dev, and provide separate production deployment guidance. |
| Dependencies | Compose profiles, `.env.example`, docs, secret policy. |
| Tests | Compose config validation, non-default secret check, volume persistence smoke test. |
| Acceptance criteria | Local stack persists data across container recreation and cannot be mistaken for a secure production deployment. |

### GAP-022: Public informational endpoints may expose operational metadata

| Field | Detail |
| --- | --- |
| Component | Public API surface |
| File | `agi_platform/security.py`, `api/main.py` |
| Current behavior | `/metrics`, `/security/policy`, `/architecture/*`, `/tools`, and `/mcp/manifest` are public. They expose route/tool/security policy metadata and metrics. |
| Risk | Attackers can enumerate capabilities, permissions, rate limits, and operational counters. Public metrics can leak traffic patterns. |
| Severity | P2 |
| Root cause | Informational routes are globally public to satisfy tests/tooling without environment-specific exposure policy. |
| Recommended implementation | Split public liveness/readiness from authenticated diagnostics. Keep `/live` public; protect `/metrics`, `/security/policy`, tool manifests, and architecture catalogs in production or serve them through an internal network/ingress. |
| Dependencies | Environment-aware public route policy, docs update, tests adjusted for production mode vs test mode. |
| Tests | Production-mode public surface tests, internal-only metrics tests, docs endpoint exposure tests. |
| Acceptance criteria | Only intended endpoints are public in production; sensitive diagnostics require auth or internal network controls. |

### GAP-023: Error handling still lacks typed exceptions and provider failure taxonomy

| Field | Detail |
| --- | --- |
| Component | API and integrations |
| File | `api/main.py`, `agi_platform/llm/core.py`, `agi_platform/github_intel/core.py`, `agi_platform/research/core.py` |
| Current behavior | Routes catch broad `Exception` for LLM/GitHub paths and convert failures to generic `503`; other provider paths may propagate through generic handler. There is no typed retryable/non-retryable taxonomy. |
| Risk | Operators cannot distinguish auth failures, quota exhaustion, provider outage, bad input, and internal bugs. Future retries may treat non-idempotent or non-retryable errors incorrectly. |
| Severity | P2 |
| Root cause | No domain exception hierarchy or adapter-level error normalization. |
| Recommended implementation | Define typed exceptions with safe messages, retry classification, provider code mapping, and telemetry labels. Preserve sanitized client messages while recording secure internal diagnostics. |
| Dependencies | Integration adapter layer, logging/redaction, telemetry. |
| Tests | Error mapping tests, no-secret error response tests, retry classification tests. |
| Acceptance criteria | Client errors are safe and actionable; internal logs classify failures without leaking secrets. |

## P0 blockers

1. Critical domain state is process-local and non-durable.
2. Workflow state uses temp JSON files without concurrency/idempotency guarantees.
3. Tenant identity is not applied to domain records or queries.
4. Authorization is route-scoped rather than resource/capability/approval-scoped.
5. Sandbox execution is subprocess-based and not a production security boundary.
6. External HTTP integrations do not consistently enforce SSRF/response policy.
7. Backup/restore and disaster recovery are absent.
8. Governance approvals are mutable, in-memory, and not globally enforced for high-risk operations.

## P1 blockers

1. LLM reliability, fallback, usage ledger, and cost controls are incomplete.
2. Readiness does not prove live dependency/capability health.
3. Migration strategy is not versioned or verified against live databases in CI.
4. Docker image is not hardened and runs as root.
5. Kubernetes lacks key security/availability controls.
6. CI/CD runs only basic tests and does not gate security/deployment/migration readiness.
7. Rate limiting is process-local and not multi-replica safe.
8. Self-improvement lacks a formal safe deployment lifecycle.
9. Observability lacks durable logs/traces/audit and production alerting.
10. Secret handling and leakage controls are incomplete.
11. Docker Compose is development-oriented and exposes stateful services with default credentials and no volumes.

## P2 improvements

1. GitHub indexing needs pagination, checkpointing, rate-limit handling, and content policy.
2. Analysis findings need durable lifecycle, fingerprints, SARIF, and broader scanners.
3. Public informational endpoints should be environment-aware and restricted in production.
4. API errors need typed exception hierarchy and provider failure taxonomy.

## Recommended implementation order

1. **Stop production-readiness ambiguity**: keep documentation explicit that the system is not production-ready while P0s exist; ensure `/ready` cannot become green without live dependency/capability checks.
2. **Build durable control plane**: implement migration tooling, Postgres repositories, tenant/identity/resource ownership, immutable events, and audit records.
3. **Enforce tenant isolation and policy authorization**: pass request context into every service, enforce resource-scoped ABAC, and add approval-gated high-risk operations.
4. **Replace unsafe execution boundary**: move sandbox execution into isolated disposable container/microVM runtime with escape/resource/secret tests.
5. **Harden outbound integrations and LLMs**: central policy HTTP client, SSRF controls, retries/circuit breakers, provider health, durable usage/cost ledger, and budgets.
6. **Make workflows recoverable**: transactional workflow/task/checkpoint stores, idempotency keys, optimistic concurrency, outbox/dead-letter handling, and failure-injection tests.
7. **Add backup/restore and migration gates**: live DB migration tests, backup jobs, restore drills, RPO/RTO, and schema drift detection.
8. **Harden deployment and CI/CD**: non-root scanned images, full Kubernetes security controls, service containers in CI, SAST/dependency/secret scans, manifest validation, and container scans.
9. **Complete observability**: structured logs, traces, durable audit/event stream, SLO dashboards, alerting, and redaction.
10. **Scale feature depth**: GitHub indexing, analysis lifecycle, public endpoint exposure policy, and typed error taxonomy.
