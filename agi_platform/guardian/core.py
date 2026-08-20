from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher


@dataclass
class MemoryGuardian:
    versions: dict[str, list[dict]] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)
    reviews: list[dict] = field(default_factory=list)

    def validate(self, candidate: dict, existing: list[dict]) -> dict:
        duplicate = None
        similarity = 0.0
        for record in existing:
            ratio = SequenceMatcher(None, candidate.get("content", ""), record.get("content", "")).ratio()
            if ratio > similarity:
                similarity = ratio
                duplicate = record
        risk_score = 0.8 if similarity > 0.9 else 0.2 if len(candidate.get("content", "")) > 20 else 0.5
        decision = "review" if risk_score >= 0.5 else "approve"
        review = {"tenant_id": candidate.get("tenant_id"), "candidate_id": candidate.get("id"), "decision": decision, "risk_score": risk_score, "duplicate_id": duplicate.get("id") if duplicate and similarity > 0.9 else None}
        self.reviews.append(review)
        return review

    def version(self, memory: dict) -> dict:
        history = self.versions.setdefault(memory["id"], [])
        entry = {"version": len(history) + 1, "memory": dict(memory)}
        history.append(entry)
        self.audit.append({"tenant_id": memory.get("tenant_id"), "memory_id": memory["id"], "action": "versioned", "version": entry["version"]})
        return entry

    def rollback(self, memory_id: str, version: int) -> dict:
        for entry in self.versions.get(memory_id, []):
            if entry["version"] == version:
                self.audit.append({"tenant_id": entry["memory"].get("tenant_id"), "memory_id": memory_id, "action": "rollback", "version": version})
                return entry["memory"]
        raise KeyError(f"version {version} not found for memory {memory_id}")
