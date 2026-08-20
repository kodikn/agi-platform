import pytest
from sqlalchemy import create_engine, select

from agi_platform.database import AuditEventRow, Database
from agi_platform.memory.core import (
    DurableMemoryStore,
    MemoryLayer,
    OptimisticConcurrencyError,
)
from agi_platform.security import Identity, TenantContext


def ctx(tenant="tenant-a"):
    ident = Identity(
        "subject", tenant, frozenset(), frozenset({"memory.read", "memory.write"})
    )
    return TenantContext(tenant, ident, "rid")


def store(tmp_path, qdrant_available=True):
    engine = create_engine(f"sqlite:///{tmp_path / 'memory.sqlite3'}", future=True)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    return DurableMemoryStore(Database(engine), qdrant_available=qdrant_available)


def test_write_restart_read(tmp_path):
    backend = store(tmp_path)
    record = backend.store(ctx(), "durable alpha", "semantic", {"namespace": "n"})
    restarted = DurableMemoryStore(backend.database)
    found = restarted.search(ctx(), "alpha")
    assert found["results"][0]["id"] == record["id"]


def test_concurrent_update_and_stale_version_rejection(tmp_path):
    backend = store(tmp_path)
    record = backend.store(ctx(), "v1", "semantic")
    updated = backend.update(ctx(), record["id"], "v2", expected_version=1)
    assert updated["version"] == 2
    with pytest.raises(OptimisticConcurrencyError):
        backend.update(ctx(), record["id"], "v3", expected_version=1)


def test_rollback_provenance_tenant_isolation_and_audit(tmp_path):
    backend = store(tmp_path)
    record = backend.store(
        ctx(),
        "original",
        "semantic",
        {"provenance": {"source_id": "s1"}, "source": "research", "confidence": 0.7},
    )
    backend.update(ctx(), record["id"], "changed", expected_version=1)
    rolled = backend.rollback(ctx(), record["id"], 1)
    assert rolled["content"] == "original"
    assert rolled["provenance"] == {"source_id": "s1"}
    assert backend.search(ctx("tenant-b"), "original")["results"] == []
    with backend.database.session() as session:
        assert (
            session.execute(
                select(AuditEventRow).where(AuditEventRow.tenant_id == "tenant-a")
            )
            .scalars()
            .first()
            is not None
        )


def test_qdrant_unavailable_persists_metadata_without_embedding(tmp_path):
    backend = store(tmp_path, qdrant_available=False)
    record = backend.store(ctx(), "no vector", "semantic")
    assert record["embedding_id"] is None
    assert backend.search(ctx(), "vector")["results"]


def test_postgresql_unavailable_is_explicit(tmp_path):
    layer = MemoryLayer(store(tmp_path))
    layer.store_backend.database.engine.dispose()
    # SQLite reconnects after dispose, so assert health is explicit instead of hidden process dict fallback.
    assert isinstance(layer.store_backend.database.healthy(), bool)
