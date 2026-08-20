from __future__ import annotations

import json
import hashlib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ExternalMemorySettings:
    enabled: bool = False
    base_url: str = ""
    api_key: str | None = None
    team_id: str | None = None
    timeout_seconds: int = 3


@dataclass(frozen=True)
class ExternalMemoryAsset:
    id: str
    asset_type: str
    title: str
    content: str
    score: float
    source: str = "tencentdb_agent_memory"
    visibility: str = "team"
    version: str = "unknown"
    metadata: dict[str, Any] | None = None

    def to_memory_result(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["memory_type"] = self.asset_type
        payload["created_at"] = 0
        payload["archived"] = False
        payload["metadata"] = self.metadata or {}
        return payload


class TencentDBMemoryConnector:
    """Read-only connector for TencentDB Agent Memory compatible services."""

    def __init__(self, settings: ExternalMemorySettings) -> None:
        self.settings = settings

    def health(self) -> dict[str, Any]:
        if not self.settings.enabled:
            return {"status": "disabled", "source": "tencentdb_agent_memory"}
        if not self.settings.base_url:
            return {"status": "not-ready", "source": "tencentdb_agent_memory", "detail": "missing base_url"}
        try:
            response = self._request("GET", "/health")
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            return {"status": "unavailable", "source": "tencentdb_agent_memory", "detail": str(exc)}
        return {"status": "ok", "source": "tencentdb_agent_memory", "upstream": response}

    def search_assets(self, query: str, agent_id: str | None = None, asset_types: list[str] | None = None, limit: int = 5) -> list[ExternalMemoryAsset]:
        if not self.settings.enabled or not self.settings.base_url:
            return []
        payload = {
            "query": query,
            "limit": limit,
            "team_id": self.settings.team_id,
            "agent_id": agent_id,
            "asset_types": asset_types or ["chat_memory", "skill", "wiki", "codegraph"],
        }
        try:
            data = self._request("POST", "/assets/search", payload)
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            return []
        raw_assets = data.get("assets", data.get("results", [])) if isinstance(data, dict) else []
        return [self._asset_from_payload(item) for item in raw_assets[:limit] if isinstance(item, dict)]

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        if not self.settings.enabled or not self.settings.base_url:
            return None
        safe_asset_id = urllib.parse.quote(asset_id, safe="")
        try:
            return self._request("GET", f"/assets/{safe_asset_id}")
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            return None

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.settings.base_url.rstrip('/')}/{path.lstrip('/')}"
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
            text = response.read().decode("utf-8")
        return json.loads(text) if text else {}

    @staticmethod
    def _asset_from_payload(payload: dict[str, Any]) -> ExternalMemoryAsset:
        content = str(payload.get("content") or payload.get("summary") or payload.get("text") or "")
        fallback_id = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        return ExternalMemoryAsset(
            id=str(payload.get("id") or payload.get("asset_id") or payload.get("external_id") or fallback_id),
            asset_type=str(payload.get("asset_type") or payload.get("type") or "external"),
            title=str(payload.get("title") or payload.get("name") or "Untitled memory asset"),
            content=content,
            score=_safe_float(payload.get("score") or payload.get("relevance") or 0.0),
            source=str(payload.get("source") or "tencentdb_agent_memory"),
            visibility=str(payload.get("visibility") or "team"),
            version=str(payload.get("version") or "unknown"),
            metadata=metadata,
        )


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
