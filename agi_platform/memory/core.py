from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from agi_platform.database import (
    AuditEventRow,
    Database,
    MemoryEvidenceRow,
    MemoryRow,
    MemoryVersionRow,
    new_id,
    now_ts,
)
from agi_platform.security import TenantContext


class OptimisticConcurrencyError(RuntimeError):
    pass


class DurableMemoryStore:
    def __init__(
        self, database: Database | None = None, qdrant_available: bool = True
    ) -> None:
        self.database = database or Database()
        self.qdrant_available = qdrant_available
        self.database.create_all()

    def store(
        self,
        context: TenantContext,
        content: str,
        memory_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.database.ensure_tenant(context.tenant_id)
        metadata = metadata or {}
        namespace = str(metadata.get("namespace", "default"))
        digest = hashlib.sha256(
            f"{context.tenant_id}:{namespace}:{memory_type}:{content}".encode()
        ).hexdigest()
        embedding_id = f"qdrant:{digest}" if self.qdrant_available else None
        provenance = metadata.get(
            "provenance", {"source": metadata.get("source", "api")}
        )
        with self.database.session() as session:
            row = session.get(MemoryRow, digest)
            if row is None:
                row = MemoryRow(
                    id=digest,
                    tenant_id=context.tenant_id,
                    namespace=namespace,
                    content=content,
                    embedding_id=embedding_id,
                    provenance=provenance,
                    source=str(metadata.get("source", "api")),
                    confidence=float(metadata.get("confidence", 1.0)),
                    retention=metadata.get("retention", {}),
                    metadata_json={**metadata, "memory_type": memory_type},
                )
                session.add(row)
                session.flush()
                session.add(
                    MemoryVersionRow(
                        tenant_id=context.tenant_id,
                        memory_id=digest,
                        version=1,
                        content=content,
                        provenance=provenance,
                    )
                )
                session.add(
                    MemoryEvidenceRow(
                        id=new_id("evidence"),
                        tenant_id=context.tenant_id,
                        memory_id=digest,
                        source=row.source,
                        evidence=provenance,
                    )
                )
            session.add(
                AuditEventRow(
                    id=new_id("audit"),
                    tenant_id=context.tenant_id,
                    actor=context.identity.subject,
                    action="memory.write",
                    target=digest,
                    result="succeeded",
                    metadata_json={"qdrant_available": self.qdrant_available},
                )
            )
            session.flush()
            return self._to_record(row)

    def search(
        self, context: TenantContext, query: str, limit: int = 5
    ) -> dict[str, Any]:
        terms = set(query.lower().split())
        with self.database.session() as session:
            rows = (
                session.execute(
                    select(MemoryRow).where(
                        MemoryRow.tenant_id == context.tenant_id,
                        MemoryRow.status == "ACTIVE",
                    )
                )
                .scalars()
                .all()
            )
            ranked = []
            for row in rows:
                tokens = set(row.content.lower().split())
                score = len(terms & tokens) / max(len(terms), 1)
                if score > 0:
                    ranked.append((score, self._to_record(row)))
            ranked.sort(key=lambda item: item[0], reverse=True)
            return {
                "query": query,
                "results": [
                    {**record, "score": score} for score, record in ranked[:limit]
                ],
            }

    def update(
        self,
        context: TenantContext,
        memory_id: str,
        content: str,
        expected_version: int,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(MemoryRow, memory_id)
            if row is None or row.tenant_id != context.tenant_id:
                raise KeyError(memory_id)
            if row.version != expected_version:
                raise OptimisticConcurrencyError("stale memory version")
            row.content = content
            row.version += 1
            row.updated_at = now_ts()
            session.add(
                MemoryVersionRow(
                    tenant_id=context.tenant_id,
                    memory_id=memory_id,
                    version=row.version,
                    content=content,
                    provenance=row.provenance,
                )
            )
            session.add(
                AuditEventRow(
                    id=new_id("audit"),
                    tenant_id=context.tenant_id,
                    actor=context.identity.subject,
                    action="memory.update",
                    target=memory_id,
                    result="succeeded",
                    metadata_json={"version": row.version},
                )
            )
            session.flush()
            return self._to_record(row)

    def rollback(
        self, context: TenantContext, memory_id: str, version: int
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(MemoryRow, memory_id)
            target = session.execute(
                select(MemoryVersionRow).where(
                    MemoryVersionRow.tenant_id == context.tenant_id,
                    MemoryVersionRow.memory_id == memory_id,
                    MemoryVersionRow.version == version,
                )
            ).scalar_one_or_none()
            if row is None or row.tenant_id != context.tenant_id or target is None:
                raise KeyError(memory_id)
            row.content = target.content
            row.version += 1
            row.updated_at = now_ts()
            session.add(
                MemoryVersionRow(
                    tenant_id=context.tenant_id,
                    memory_id=memory_id,
                    version=row.version,
                    content=row.content,
                    provenance=target.provenance,
                )
            )
            session.add(
                AuditEventRow(
                    id=new_id("audit"),
                    tenant_id=context.tenant_id,
                    actor=context.identity.subject,
                    action="memory.rollback",
                    target=memory_id,
                    result="succeeded",
                    metadata_json={"to_version": version},
                )
            )
            session.flush()
            return self._to_record(row)

    def consolidate(self, context: TenantContext) -> dict[str, Any]:
        with self.database.session() as session:
            rows = (
                session.execute(
                    select(MemoryRow).where(
                        MemoryRow.tenant_id == context.tenant_id,
                        MemoryRow.status == "ACTIVE",
                    )
                )
                .scalars()
                .all()
            )
            by_type: dict[str, list[str]] = {}
            for row in rows:
                by_type.setdefault(
                    row.metadata_json.get("memory_type", "semantic"), []
                ).append(row.content)
            return {
                "summaries": {
                    key: " ".join(values)[:500] for key, values in by_type.items()
                },
                "record_count": len(rows),
            }

    def _to_record(self, row: MemoryRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "namespace": row.namespace,
            "content": row.content,
            "memory_type": row.metadata_json.get("memory_type", "semantic"),
            "metadata": row.metadata_json,
            "embedding_id": row.embedding_id,
            "provenance": row.provenance,
            "source": row.source,
            "confidence": row.confidence,
            "version": row.version,
            "status": row.status,
            "retention": row.retention,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "archived": row.status != "ACTIVE",
        }


@dataclass
class MemoryLayer:
    store_backend: DurableMemoryStore = field(default_factory=DurableMemoryStore)

    @property
    def records(self):
        class RecordsProxy:
            def __init__(self, backend: DurableMemoryStore) -> None:
                self.backend = backend

            def clear(self) -> None:
                from agi_platform.database import (
                    AuditEventRow,
                    MemoryEvidenceRow,
                    MemoryRow,
                    MemoryVersionRow,
                )

                with self.backend.database.session() as session:
                    session.query(AuditEventRow).delete()
                    session.query(MemoryEvidenceRow).delete()
                    session.query(MemoryVersionRow).delete()
                    session.query(MemoryRow).delete()

            def values(self):
                with self.backend.database.session() as session:
                    return [
                        self.backend._to_record(row)
                        for row in session.execute(select(MemoryRow)).scalars().all()
                    ]

        return RecordsProxy(self.store_backend)

    def store(
        self,
        content: str,
        memory_type: str,
        metadata: dict[str, Any] | None = None,
        context: TenantContext | None = None,
    ) -> dict[str, Any]:
        if context is None:
            raise PermissionError("tenant context required")
        return self.store_backend.store(context, content, memory_type, metadata)

    def search(
        self, query: str, limit: int = 5, context: TenantContext | None = None
    ) -> dict[str, Any]:
        if context is None:
            raise PermissionError("tenant context required")
        return self.store_backend.search(context, query, limit)

    def update(
        self,
        memory_id: str,
        content: str,
        expected_version: int,
        context: TenantContext | None = None,
    ) -> dict[str, Any]:
        if context is None:
            raise PermissionError("tenant context required")
        return self.store_backend.update(context, memory_id, content, expected_version)

    def rollback(
        self, memory_id: str, version: int, context: TenantContext | None = None
    ) -> dict[str, Any]:
        if context is None:
            raise PermissionError("tenant context required")
        return self.store_backend.rollback(context, memory_id, version)

    def consolidate(self, context: TenantContext | None = None) -> dict[str, Any]:
        if context is None:
            raise PermissionError("tenant context required")
        return self.store_backend.consolidate(context)
