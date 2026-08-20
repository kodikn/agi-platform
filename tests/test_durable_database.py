from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError

from agi_platform.database import Base, Database, MemoryRow, TenantRow

MIGRATION = Path("migrations/003_durable_application_state.sql").read_text()


def sqlite_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite3'}", future=True)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    db = Database(engine)
    db.create_all()
    return db


def test_fresh_install_creates_durable_tables(tmp_path):
    db = sqlite_db(tmp_path)
    tables = set(Base.metadata.tables)
    assert {
        "tenants",
        "memories",
        "memory_versions",
        "memory_evidence",
        "audit_events",
        "workflows",
        "workflow_tasks",
        "workflow_checkpoints",
        "workflow_events",
    } <= tables
    db.ensure_tenant("tenant-a")
    with db.session() as session:
        assert session.get(TenantRow, "tenant-a") is not None


def test_upgrade_migration_is_additive_and_documents_backfill():
    for ddl in (
        "CREATE TABLE IF NOT EXISTS workflow_tasks",
        "CREATE TABLE IF NOT EXISTS workflow_attempts",
        "CREATE TABLE IF NOT EXISTS llm_requests",
        "CREATE TABLE IF NOT EXISTS sandbox_runs",
        "CREATE TABLE IF NOT EXISTS research_sources",
    ):
        assert ddl in MIGRATION
    assert "Existing data migration" in MIGRATION
    assert "DROP TABLE" not in MIGRATION.upper()


def test_constraints_fk_unique_and_tenant_isolation(tmp_path):
    db = sqlite_db(tmp_path)
    db.ensure_tenant("tenant-a")
    with db.session() as session:
        session.add(
            MemoryRow(id="m1", tenant_id="tenant-a", namespace="n", content="one")
        )
    with pytest.raises(IntegrityError):
        with db.session() as session:
            session.add(
                MemoryRow(id="m2", tenant_id="missing", namespace="n", content="bad")
            )
    with pytest.raises(IntegrityError):
        with db.session() as session:
            session.add(
                MemoryRow(id="m1", tenant_id="tenant-a", namespace="n", content="dupe")
            )
    with db.session() as session:
        visible = (
            session.execute(select(MemoryRow).where(MemoryRow.tenant_id == "tenant-a"))
            .scalars()
            .all()
        )
        invisible = (
            session.execute(select(MemoryRow).where(MemoryRow.tenant_id == "tenant-b"))
            .scalars()
            .all()
        )
    assert len(visible) == 1
    assert invisible == []


def test_transaction_rollback(tmp_path):
    db = sqlite_db(tmp_path)
    db.ensure_tenant("tenant-a")
    with pytest.raises(RuntimeError):
        with db.session() as session:
            session.add(
                MemoryRow(
                    id="rollback", tenant_id="tenant-a", namespace="n", content="temp"
                )
            )
            raise RuntimeError("boom")
    with db.session() as session:
        assert session.get(MemoryRow, "rollback") is None
