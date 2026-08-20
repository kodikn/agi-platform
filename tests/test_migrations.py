from pathlib import Path


MIGRATION = Path("migrations/001_platform_schema.sql").read_text()
IDENTITY_MIGRATION = Path("migrations/002_identity_schema.sql").read_text()


def test_control_plane_tables_are_declared_for_postgres():
    for table in (
        "tenants",
        "users",
        "agents",
        "agent_roles",
        "tools",
        "tool_permissions",
        "workflows",
        "workflow_runs",
        "tasks",
        "task_runs",
        "checkpoints",
        "events",
        "audit_events",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in MIGRATION


def test_event_store_has_idempotency_and_replay_constraints():
    assert "event_id TEXT PRIMARY KEY" in MIGRATION
    assert "UNIQUE (tenant_id, workflow_id, sequence)" in MIGRATION
    assert "idx_events_tenant_workflow_sequence" in MIGRATION
    assert "correlation_id TEXT" in MIGRATION
    assert "request_id TEXT" in MIGRATION


def test_workflow_schema_has_tenant_state_and_optimistic_versioning():
    assert "tenant_id TEXT NOT NULL REFERENCES tenants(id)" in MIGRATION
    assert "CHECK (state IN ('CREATED', 'PLANNED', 'RUNNING', 'WAITING', 'PAUSED', 'FAILED', 'RECOVERING', 'COMPLETED', 'CANCELLED'))" in MIGRATION
    assert "version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0)" in MIGRATION
    assert "UNIQUE (tenant_id, idempotency_key)" in MIGRATION


def test_identity_schema_hashes_and_scopes_api_keys():
    for table in (
        "service_accounts",
        "permissions",
        "roles",
        "role_permissions",
        "user_roles",
        "service_account_roles",
        "api_keys",
        "api_key_audit_events",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in IDENTITY_MIGRATION
    assert "key_hash TEXT NOT NULL" in IDENTITY_MIGRATION
    assert "scopes JSONB NOT NULL DEFAULT '[]'" in IDENTITY_MIGRATION
    assert "revoked BOOLEAN NOT NULL DEFAULT false" in IDENTITY_MIGRATION
    assert "expires_at TIMESTAMPTZ" in IDENTITY_MIGRATION
    assert "UNIQUE (tenant_id, key_hash)" in IDENTITY_MIGRATION
    assert "idx_api_keys_tenant_active" in IDENTITY_MIGRATION
