from pathlib import Path


MIGRATION = Path("migrations/001_platform_schema.sql").read_text()


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
