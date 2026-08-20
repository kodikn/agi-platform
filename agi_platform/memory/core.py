from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryLayer:
    records: dict[str, dict[str, Any]] = field(default_factory=dict)

    def store(self, content: str, memory_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = metadata or {}
        digest = hashlib.sha256(f"{memory_type}:{content}".encode()).hexdigest()
        record = {"id": digest, "content": content, "memory_type": memory_type, "metadata": metadata, "created_at": int(time.time()), "archived": False}
        self.records[digest] = record
        return record

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        terms = set(query.lower().split())
        ranked = []
        for record in self.records.values():
            tokens = set(record["content"].lower().split())
            score = len(terms & tokens) / max(len(terms), 1)
            if score > 0:
                ranked.append((score, record))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return {"query": query, "results": [{**record, "score": score} for score, record in ranked[:limit]]}

    def consolidate(self) -> dict[str, Any]:
        by_type: dict[str, list[str]] = {}
        for record in self.records.values():
            by_type.setdefault(record["memory_type"], []).append(record["content"])
        summaries = {key: " ".join(values)[:500] for key, values in by_type.items()}
        return {"summaries": summaries, "record_count": len(self.records)}
