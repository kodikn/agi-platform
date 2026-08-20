# Multi-Tenant Identity and Authorization

Request flow is: request → authentication → identity → tenant context → authorization.

* API keys are compared by SHA-256 hash only and can be tenant-bound, scoped, revoked, rotated, and expired.
* `X-Tenant-ID` is optional narrowing input. It must match the authenticated identity tenant and can never switch tenants.
* Tenant-aware services require `TenantContext`; missing context fails closed.
* The centralized `PolicyEngine.authorize(subject, tenant, action, resource, context)` denies by default, checks tenant/resource ownership, requires explicit permissions, and requires approval for high-risk actions.
* Governance authorization decisions are written to the in-process audit trail; production deployments should persist these events to `audit_events` / `api_key_audit_events`.

## Permissions

`memory.read`, `memory.write`, `memory.delete`, `workflow.read`, `workflow.start`, `workflow.cancel`, `github.read`, `github.index`, `graph.read`, `graph.write`, `sandbox.execute`, `governance.propose`, `governance.review`, `governance.approve`, `evolution.propose`, `evolution.approve`, `evolution.deploy`, `production.mutate`.

## Remaining security risks

* In-memory stores are tenant-filtered for tests/prototype use, but production must enforce row-level security in the database.
* Bootstrap plaintext keys in environment variables are accepted for local tests; production should provision only `key_hash` values through a secret manager.
* Approval context currently checks the presence of an approval identifier; production should verify approval records cryptographically or in a durable workflow.


## Durable database migration notes

Migrations use additive SQL files under `migrations/` to stay compatible with the repository's current migration mechanism. `003_durable_application_state.sql` is intentionally non-destructive: it creates missing tables/indexes and adds nullable/defaulted columns needed for durable memory and workflow metadata. Existing rows with missing `tenant_id` must be backfilled to an explicit legacy tenant before any future migration tightens `tenant_id` to `NOT NULL` on old prototype tables.

PostgreSQL is the production source of truth for memory metadata, workflow state, audit events, governance decisions, LLM accounting, sandbox runs, and research evidence. Qdrant stores vectors only; when Qdrant is unavailable, memory writes still persist metadata with `embedding_id = null` and audit metadata records the degraded vector state.

 main
