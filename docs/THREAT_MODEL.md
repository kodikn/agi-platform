# Threat Model

## Protected assets

Tenant data, API keys, provider credentials, database connection strings, memory records, workflow state, audit records, sandbox host boundary, model prompts/responses, repository content, and governance approvals.

## Primary threats and controls

| Threat | Control | Regression coverage |
| --- | --- | --- |
| Authentication bypass | API key validation, revoked/expired checks | `tests/test_authz.py`, `tests/test_security_regressions.py` |
| Authorization bypass / tenant escape / IDOR | Route permission map and tenant context | `tests/test_multi_tenant_identity.py`, `tests/test_security_regressions.py` |
| SSRF / DNS rebinding | outbound URL validation and private network deny rules | `tests/test_ssrf.py` |
| RCE / command injection / sandbox escape | sandbox deny rules and production container/microVM requirement | `tests/test_sandbox_security.py`, `tests/test_security_regressions.py` |
| Secret leakage | canonical errors and JSON log redaction | `tests/test_api_errors.py`, `tests/test_observability.py` |
| Rate-limit bypass | Redis counters across replicas and fail-closed sensitive scopes | `tests/test_distributed_security.py` |
| Prompt injection / malicious tool output / memory poisoning | policy tests prevent instructions from granting permissions | `tests/test_security_regressions.py` |
| Workflow races / duplicate side effects | Redis distributed locks and workflow leases/idempotency | `tests/test_distributed_security.py`, `tests/test_durable_workflow.py` |
