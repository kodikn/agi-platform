from __future__ import annotations

import ipaddress
import json
import socket
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from fastapi import Request


@dataclass(frozen=True)
class Identity:
    subject: str
    tenant_id: str
    roles: frozenset[str]
    permissions: frozenset[str]
    key_id: str = ""

    def can(self, permission: str) -> bool:
        return "*" in self.permissions or permission in self.permissions


@dataclass(frozen=True)
class APIKeyRecord:
    key: str
    subject: str
    tenant_id: str
    roles: frozenset[str]
    permissions: frozenset[str]
    key_id: str


PERMISSION_BY_ROUTE: dict[tuple[str, str], str] = {
    ("POST", "/chat"): "llm:invoke",
    ("POST", "/completion"): "llm:invoke",
    ("POST", "/embeddings"): "llm:invoke",
    ("GET", "/models"): "llm:read",
    ("POST", "/memory/store"): "memory:write",
    ("POST", "/memory/search"): "memory:read",
    ("POST", "/memory/retrieve"): "memory:read",
    ("POST", "/memory/consolidate"): "memory:write",
    ("POST", "/guardian/validate"): "memory:write",
    ("GET", "/guardian/audit"): "audit:read",
    ("POST", "/research/query"): "research:read",
    ("POST", "/research/report"): "research:read",
    ("POST", "/chinese/articles"): "research:write",
    ("POST", "/chinese/analyze"): "research:read",
    ("POST", "/analyze/code"): "analysis:execute",
    ("POST", "/analyze/repository"): "analysis:execute",
    ("POST", "/github/repositories"): "github:index",
    ("POST", "/sandbox/execute"): "sandbox:execute",
    ("POST", "/graph/entities"): "graph:write",
    ("POST", "/graph/relationships"): "graph:write",
    ("POST", "/graph/search"): "graph:read",
    ("POST", "/orchestrate"): "workflow:create",
    ("POST", "/governance/proposals"): "governance:propose",
    ("POST", "/governance/reviews"): "governance:approve",
    ("POST", "/evolution/evaluate"): "evolution:propose",
    ("POST", "/evolution/proposals"): "evolution:propose",
}
DYNAMIC_PREFIX_PERMISSIONS = (("GET", "/github/repositories/", "github:read"), ("POST", "/orchestrate/", "workflow:execute"))


@dataclass
class RateLimiter:
    limit_per_minute: int
    windows: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def allow(self, identity: str) -> bool:
        now = time.time()
        window = self.windows[identity]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= self.limit_per_minute:
            return False
        window.append(now)
        return True


def parse_api_keys(raw: str | None, legacy_key: str | None) -> dict[str, APIKeyRecord]:
    records: dict[str, APIKeyRecord] = {}
    if raw:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("AGI_API_KEYS must be a JSON list")
        for index, item in enumerate(data):
            key = str(item["key"])
            records[key] = APIKeyRecord(
                key=key,
                subject=str(item.get("subject") or f"service-account-{index}"),
                tenant_id=str(item["tenant_id"]),
                roles=frozenset(item.get("roles", ["service"])),
                permissions=frozenset(item.get("permissions", [])),
                key_id=str(item.get("key_id") or f"key-{index}"),
            )
    if legacy_key and legacy_key not in records:
        records[legacy_key] = APIKeyRecord(legacy_key, "legacy-api-key", "legacy", frozenset({"admin"}), frozenset({"*"}), "legacy")
    return records


def route_permission(method: str, path: str) -> str | None:
    permission = PERMISSION_BY_ROUTE.get((method, path))
    if permission:
        return permission
    for expected_method, prefix, dynamic_permission in DYNAMIC_PREFIX_PERMISSIONS:
        if method == expected_method and path.startswith(prefix):
            return dynamic_permission
    return None


def authenticate_request(request: Request, api_keys: dict[str, APIKeyRecord]) -> Identity | None:
    raw_key = request.headers.get("X-API-Key")
    if not raw_key:
        return None
    record = api_keys.get(raw_key)
    if not record:
        return None
    tenant_header = request.headers.get("X-Tenant-ID")
    if tenant_header and tenant_header != record.tenant_id:
        return None
    return Identity(record.subject, record.tenant_id, record.roles, record.permissions, record.key_id)


def canonical_error(code: str, message: str, request_id: str, status_code: int):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "request_id": request_id}})


def security_headers() -> dict[str, str]:
    return {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Permissions-Policy": "geolocation=(), microphone=(), camera=()", "Cache-Control": "no-store"}


def apply_production_headers(response, service_name: str):
    for key, value in security_headers().items():
        response.headers[key] = value
    response.headers["X-Service-Name"] = service_name
    return response


def public_paths() -> set[str]:
    return {"/", "/health", "/live", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"}


BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}
BLOCKED_NETWORKS = tuple(ipaddress.ip_network(cidr) for cidr in ("0.0.0.0/8", "10.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16", "::1/128", "fc00::/7", "fe80::/10"))


def validate_outbound_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("outbound URL scheme is not allowed")
    if not parsed.hostname:
        raise ValueError("outbound URL host is required")
    host = parsed.hostname.strip().lower().rstrip(".")
    if host in BLOCKED_HOSTS:
        raise ValueError("outbound URL host is blocked")
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValueError("outbound URL host could not be resolved") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if any(ip in network for network in BLOCKED_NETWORKS) or ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValueError("outbound URL resolves to a blocked network")
    return url


def request_id() -> str:
    return uuid.uuid4().hex
