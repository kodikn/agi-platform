# Production Certification

Certification date: 2026-08-20. This repository is **not yet production certified**. The table below intentionally avoids PASS where evidence is incomplete.

| Area | Status | Evidence | Remediation |
| --- | --- | --- | --- |
| Architecture | PARTIAL | Twelve levels and service boundaries exist, but many are in-process implementations. | Implement durable domain/event/persistence layers per audit. |
| Security | FAIL | Optional API key only; no scoped authorization/tenant isolation; sandbox not strongly isolated. | Add identity, policy engine, approvals, isolated sandbox. |
| Testing | PARTIAL | Pytest API/level tests exist and pass. | Add failure, security, integration, property, E2E, and load tests. |
| Observability | PARTIAL | Prometheus-style counters and headers exist. | Add structured logs, correlation IDs, traces, dependency metrics. |
| Performance | FAIL | No load baseline. | Add reproducible load tests for HTTP/workflow/tool/sandbox concurrency. |
| Reliability | PARTIAL | Workflow JSON file checkpoints exist. | Move to transactional state with idempotency, locks, retries, dead-letter, crash recovery. |
| Backup/Recovery | FAIL | No backup/restore procedure or restore test. | Document and test Postgres/Qdrant/Neo4j/artifact restore. |
| Deployment | PARTIAL | Docker Compose and minimal Kubernetes deployment exist. | Harden Docker image, add NetworkPolicy/HPA/PDB/RBAC/CI validation. |
| Data protection | FAIL | Tenant_id/provenance/retention not enforced in storage. | Add canonical schemas, retention, redaction, tenant isolation. |
| Agent safety | FAIL | Agents are planned as dict roles with no scoped budgets/permissions runtime. | Enforce agent capability model and tool budgets. |
| Sandbox safety | FAIL | Subprocess resource limits are not strong isolation. | Replace with container/microVM sandbox and escape tests. |
| Governance | FAIL | Decisions are in-memory and low risk auto-approves. | Durable ADRs, explicit scoped approvals, policy gates. |
| Self-improvement | PARTIAL | Current engine proposes only and does not mutate production. | Formalize gated lifecycle with reversible deployments. |

## Production readiness score

Current honest score: **28/100**.

Rationale: core API skeleton, tests, deployment files, basic metrics, and some real provider calls exist, but critical production controls for durable state, authorization, sandbox isolation, event/audit durability, dependency readiness, and recovery are missing or partial.
