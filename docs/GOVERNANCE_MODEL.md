# Self-Improvement Governance Model

Self-improvement is advisory by default and cannot directly modify production. Any protected action (`deploy`, production mutation, security-policy change, authorization change, or credential access) must pass this lifecycle:

`PROPOSAL -> EVALUATION -> BENCHMARK -> RISK_ASSESSMENT -> APPROVAL -> SANDBOX -> CANARY -> DEPLOY -> MONITOR -> ROLLBACK`

Durable production implementations must persist proposal, evaluation, benchmark, risk assessment, approval, deployment, rollback, and immutable audit records. The in-repository engine models the gates and denies deployment unless benchmark and explicit unexpired same-tenant approval requirements are satisfied.

Agents do not receive implicit permissions to deploy, mutate production, modify authorization/security policy, or access credentials. Every allowed or denied lifecycle action appends an audit event with tenant, actor, action, resource, result, and timestamp.
