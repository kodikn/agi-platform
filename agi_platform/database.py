from __future__ import annotations

import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def now_ts() -> int:
    return int(time.time())


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class TenantRow(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(Integer, default=now_ts)
    updated_at: Mapped[int] = mapped_column(Integer, default=now_ts)
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','SUSPENDED','DELETED')", name="tenant_status"
        ),
        CheckConstraint("version > 0", name="tenant_version"),
    )


class MemoryRow(Base):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )
    namespace: Mapped[str] = mapped_column(String, default="default")
    content: Mapped[str] = mapped_column(Text)
    embedding_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String, default="api")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    retention: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(Integer, default=now_ts)
    updated_at: Mapped[int] = mapped_column(Integer, default=now_ts)
    __table_args__ = (
        UniqueConstraint("tenant_id", "namespace", "id"),
        CheckConstraint(
            "status IN ('ACTIVE','ARCHIVED','DELETED')", name="memory_status"
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="memory_confidence"
        ),
        CheckConstraint("version > 0", name="memory_version"),
    )


class MemoryVersionRow(Base):
    __tablename__ = "memory_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )
    memory_id: Mapped[str] = mapped_column(
        String, ForeignKey("memories.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[int] = mapped_column(Integer, default=now_ts)
    __table_args__ = (UniqueConstraint("tenant_id", "memory_id", "version"),)


class MemoryEvidenceRow(Base):
    __tablename__ = "memory_evidence"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )
    memory_id: Mapped[str] = mapped_column(
        String, ForeignKey("memories.id", ondelete="CASCADE")
    )
    source: Mapped[str] = mapped_column(String)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[int] = mapped_column(Integer, default=now_ts)


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String)
    result: Mapped[str] = mapped_column(String)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[int] = mapped_column(Integer, default=now_ts)
    __table_args__ = (
        CheckConstraint(
            "result IN ('allowed','denied','succeeded','failed')", name="audit_result"
        ),
    )


class WorkflowRow(Base):
    __tablename__ = "workflows"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )
    task: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(Integer, default=now_ts)
    updated_at: Mapped[int] = mapped_column(Integer, default=now_ts)
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','WAITING','SUCCEEDED','FAILED','CANCELLED','TIMED_OUT','RECOVERING')",
            name="workflow_status",
        ),
        CheckConstraint("version > 0", name="workflow_version"),
    )


class WorkflowTaskRow(Base):
    __tablename__ = "workflow_tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )
    workflow_id: Mapped[str] = mapped_column(
        String, ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    agent: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    lease_owner: Mapped[str | None] = mapped_column(String, nullable=True)
    lease_expires_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    idempotency_key: Mapped[str] = mapped_column(String)
    created_at: Mapped[int] = mapped_column(Integer, default=now_ts)
    updated_at: Mapped[int] = mapped_column(Integer, default=now_ts)
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','WAITING','SUCCEEDED','FAILED','CANCELLED','TIMED_OUT','RECOVERING')",
            name="workflow_task_status",
        ),
    )


class WorkflowEventRow(Base):
    __tablename__ = "workflow_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )
    workflow_id: Mapped[str] = mapped_column(
        String, ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String)
    sequence: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[int] = mapped_column(Integer, default=now_ts)
    __table_args__ = (UniqueConstraint("tenant_id", "workflow_id", "sequence"),)


class WorkflowCheckpointRow(Base):
    __tablename__ = "workflow_checkpoints"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )
    workflow_id: Mapped[str] = mapped_column(
        String, ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(Integer, default=now_ts)


def default_database_url() -> str:
    configured = os.getenv("AGI_DURABLE_DATABASE_URL")
    if configured:
        return configured
    path = Path(tempfile.gettempdir()) / "agi-platform" / "durable.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def make_engine(url: str | None = None) -> Engine:
    engine = create_engine(url or default_database_url(), future=True)
    if engine.dialect.name == "sqlite":
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    return engine


class Database:
    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or make_engine()
        self.SessionLocal = sessionmaker(
            self.engine, expire_on_commit=False, future=True
        )

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def ensure_tenant(self, tenant_id: str, name: str | None = None) -> None:
        self.create_all()
        with self.session() as session:
            if session.get(TenantRow, tenant_id) is None:
                session.add(TenantRow(id=tenant_id, name=name or tenant_id))

    def healthy(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(select(1))
            return True
        except SQLAlchemyError:
            return False
