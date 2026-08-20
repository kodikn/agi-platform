from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryLayer:
    records: dict[str, dict[str, Any]] = field(default_factory=dict)

    def store(self, content: str, memory_type: str, metadata: dict[str, Any] | None = None, tenant_id: str = "default") -> dict[str, Any]:
        metadata = metadata or {}
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        digest = hashlib.sha256(f"{tenant_id}:{memory_type}:{content}".encode()).hexdigest()
        record = {
            "id": digest,
            "memory_id": digest,
            "tenant_id": tenant_id,
            "content": content,
            "content_hash": content_hash,
            "memory_type": memory_type,
            "metadata": metadata,
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            "version": 1,
            "status": "active",
            "archived": False,
        }
        self.records[digest] = record
        return record

    def search(self, query: str, limit: int = 5, tenant_id: str = "default") -> dict[str, Any]:
        terms = set(query.lower().split())
        ranked = []
        for record in self.records.values():
            if record.get("tenant_id") != tenant_id:
                continue
            tokens = set(record["content"].lower().split())
            score = len(terms & tokens) / max(len(terms), 1)
            if score > 0:
                ranked.append((score, record))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return {"query": query, "tenant_id": tenant_id, "results": [{**record, "score": score} for score, record in ranked[:limit]]}

    def consolidate(self, tenant_id: str = "default") -> dict[str, Any]:
        by_type: dict[str, list[str]] = {}
        for record in self.records.values():
            if record.get("tenant_id") != tenant_id:
                continue
            by_type.setdefault(record["memory_type"], []).append(record["content"])
        summaries = {key: " ".join(values)[:500] for key, values in by_type.items()}
        return {"tenant_id": tenant_id, "summaries": summaries, "record_count": sum(len(values) for values in by_type.values())}
