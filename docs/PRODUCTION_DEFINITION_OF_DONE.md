# Production Definition of Done

A level is production-ready only when every critical control below is implemented, tested, observable, documented, and recoverable. Static endpoint presence is not sufficient.

| Level | Runtime implementation | API contract | Database/schema ownership | Input validation | Authorization | Error handling | Observability | Metrics | Auditability | Tests | Failure tests | Security tests | Documentation | Deployment support | Recovery strategy | Current status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 LLM Core | Real provider calls exist | `/chat`, `/completion`, `/embeddings`, `/models` | Declared, not fully persisted | Partial Pydantic | Missing policy authz | Broad errors | Partial | Partial | Missing durable usage | Partial | Missing | Missing prompt/tool injection | Partial | Basic | Missing circuit recovery | YELLOW |
| 1 Memory | In-process | `/memory/*` | Declared only | Partial | Missing tenant authz | Partial | Partial | Partial | Via in-memory guardian | Partial | Missing restart tests | Missing cross-tenant tests | Partial | Basic | Missing durable recovery | RED |
| 2 Guardian | In-process | `/guardian/*` | Declared only | Partial | Missing | Partial | Partial | Partial | In-memory only | Partial | Missing | Missing | Partial | Basic | Missing | RED |
| 3 Research | Real HTTP/GitHub path | `/research/*` | Declared only | Partial | Missing source policy | Partial | Partial | Partial | Evidence not durable | Partial | Missing provider failure tests | Missing SSRF tests | Partial | Basic | Missing checkpoints | YELLOW |
| 4 Chinese Hub | Translation path when configured | `/chinese/*` | Declared only | Partial | Missing | Partial | Partial | Partial | Provenance partial | Partial | Missing | Missing untrusted content tests | Partial | Basic | Missing | YELLOW |
| 5 Analysis | Deterministic regex/AST | `/analyze/*` | Declared only | Partial | Missing | Partial | Partial | Partial | Missing durable finding lifecycle | Partial | Missing | Partial | Partial | Basic | Missing | YELLOW |
| 6 GitHub | Real GitHub API path | `/github/*` | Declared only | URL host validation | Missing repo policy | Partial | Partial | Partial | Missing durable index events | Partial | Missing rate-limit tests | Missing secret handling tests | Partial | Basic | Missing incremental recovery | YELLOW |
| 7 Sandbox | Subprocess + resource limits | `/sandbox/execute` | Declared only | Partial command allowlist | Missing scoped tool authz | Partial | Partial | Partial | Missing durable execution audit | Partial | Missing crash tests | Missing escape tests | Partial | Basic | Missing artifact recovery | RED |
| 8 Graph | In-process | `/graph/*` | Declared only | Partial | Missing tenant authz | Partial | Partial | Partial | Missing provenance | Partial | Missing | Missing traversal tests | Partial | Basic | Missing | RED |
| 9 Orchestrator | JSON-file workflow execution | `/orchestrate/*` | Declared only | Partial | Missing agent/tool authz | Partial | Partial | Partial | Events in JSON object | Partial | Partial restart semantics | Missing double-exec tests | Partial | Basic | Partial | YELLOW |
| 10 Governance | In-process decisions | `/governance/*` | Declared only | Partial | Missing approval scopes | Partial | Partial | Partial | In-memory only | Partial | Missing | Missing bypass tests | Partial | Basic | Missing | RED |
| 11 Self Improvement | Proposal-only | `/evolution/*` | Declared only | Partial | Missing lifecycle gates | Partial | Partial | Partial | Missing immutable proposal events | Partial | Missing rollback tests | Missing mutation-block tests | Partial | Basic | Missing | YELLOW |

## Critical controls

A level must remain RED when any of these is absent: durable ownership for critical state, tenant isolation for tenant-scoped data, authorization for dangerous operations, real dependency/capability readiness, auditable events for mutations, and recovery tests for stateful workflows.
