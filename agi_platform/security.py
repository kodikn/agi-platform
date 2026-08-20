from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import socket
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from fastapi import Request


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    name: str
    active: bool = True


@dataclass(frozen=True)
class User:
    user_id: str
    tenant_id: str
    email: str
    active: bool = True


@dataclass(frozen=True)
class ServiceAccount:
    service_account_id: str
    tenant_id: str
    subject: str
    active: bool = True


@dataclass(frozen=True)
class Permission:
    name: str
    description: str = ""


@dataclass(frozen=True)
class Role:
    name: str
    tenant_id: str
    permissions: frozenset[str]


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    subject: str
    key_id: str
    roles: frozenset[str]
    permissions: frozenset[str]
    service_account_id: str | None = None
    user_id: str | None = None

    def can(self, permission: str) -> bool:
        return "*" in self.permissions or permission in self.permissions


Identity = TenantContext


@dataclass(frozen=True)
class APIKeyRecord:
    key_hash: str
    subject: str
    tenant_id: str
    roles: frozenset[str]
    permissions: frozenset[str]
    key_id: str
    service_account_id: str | None = None
    user_id: str | None = None
    revoked: bool = False
    expires_at: int | None = None
    previous_key_hashes: frozenset[str] = frozenset()
    created_at: int = field(default_factory=lambda: int(time.time()))

    def is_expired(self, now: int | None = None) -> bool:
        return self.expires_at is not None and (now or int(time.time())) >= self.expires_at

    def matches(self, raw_key: str) -> bool:
        candidate = hash_api_key(raw_key)
        return hmac.compare_digest(candidate, self.key_hash) or any(hmac.compare_digest(candidate, old) for old in self.previous_key_hashes)


@dataclass
class IdentityRegistry:
    tenants: dict[str, Tenant] = field(default_factory=dict)
    users: dict[str, User] = field(default_factory=dict)
    service_accounts: dict[str, ServiceAccount] = field(default_factory=dict)
    roles: dict[tuple[str, str], Role] = field(default_factory=dict)
    permissions: dict[str, Permission] = field(default_factory=dict)
    api_keys: dict[str, APIKeyRecord] = field(default_factory=dict)
    audit_trail: list[dict[str, Any]] = field(default_factory=list)

    def authenticate(self, raw_key: str | None, requested_tenant_id: str | None = None) -> TenantContext | None:
        if not raw_key:
            self._audit("api_key.missing", None, None, "denied")
            return None
        record = next((item for item in self.api_keys.values() if item.matches(raw_key)), None)
        if record is None:
            self._audit("api_key.invalid", None, requested_tenant_id, "denied")
            return None
        if record.revoked:
            self._audit("api_key.revoked", record.key_id, record.tenant_id, "denied")
            return None
        if record.is_expired():
            self._audit("api_key.expired", record.key_id, record.tenant_id, "denied")
            return None
        tenant = self.tenants.get(record.tenant_id)
        if tenant is not None and not tenant.active:
            self._audit("tenant.inactive", record.key_id, record.tenant_id, "denied")
            return None
        if requested_tenant_id and requested_tenant_id != record.tenant_id:
            self._audit("tenant.mismatch", record.key_id, requested_tenant_id, "denied")
            return None
        self._audit("api_key.authenticated", record.key_id, record.tenant_id, "allowed")
        return TenantContext(
            tenant_id=record.tenant_id,
            subject=record.subject,
            key_id=record.key_id,
            roles=record.roles,
            permissions=record.permissions,
            service_account_id=record.service_account_id,
            user_id=record.user_id,
        )

    def _audit(self, action: str, key_id: str | None, tenant_id: str | None, result: str) -> None:
        self.audit_trail.append({"action": action, "key_id": key_id, "tenant_id": tenant_id, "result": result, "timestamp": int(time.time())})


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


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _parse_expires_at(value: object) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value)
    if text.isdigit():
        return int(text)
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC).timestamp())


def parse_api_keys(raw: str | None, legacy_key: str | None) -> IdentityRegistry:
    registry = IdentityRegistry()
    data: list[dict[str, Any]] = []
    if raw:
        loaded = json.loads(raw)
        if not isinstance(loaded, list):
            raise ValueError("AGI_API_KEYS must be a JSON list")
        data = loaded
    if legacy_key:
        data.append({"key": legacy_key, "key_id": "legacy", "subject": "legacy-api-key", "tenant_id": "legacy", "roles": ["admin"], "permissions": ["*"], "service_account_id": "legacy"})

    for index, item in enumerate(data):
        tenant_id = str(item["tenant_id"])
        subject = str(item.get("subject") or f"service-account-{index}")
        key_id = str(item.get("key_id") or f"key-{index}")
        service_account_id = str(item.get("service_account_id") or subject)
        roles = frozenset(str(role) for role in item.get("roles", ["service"]))
        permissions = frozenset(str(permission) for permission in item.get("permissions", []))
        for permission in permissions:
            registry.permissions.setdefault(permission, Permission(permission))
        for role in roles:
            registry.roles.setdefault((tenant_id, role), Role(role, tenant_id, permissions))
        registry.tenants.setdefault(tenant_id, Tenant(tenant_id, str(item.get("tenant_name") or tenant_id), bool(item.get("tenant_active", True))))
        registry.service_accounts.setdefault(service_account_id, ServiceAccount(service_account_id, tenant_id, subject, bool(item.get("active", True))))
        previous_hashes = frozenset(hash_api_key(str(key)) for key in item.get("previous_keys", []))
        registry.api_keys[key_id] = APIKeyRecord(
            key_hash=str(item.get("key_hash") or hash_api_key(str(item["key"]))),
            subject=subject,
            tenant_id=tenant_id,
            roles=roles,
            permissions=permissions,
            key_id=key_id,
            service_account_id=service_account_id,
            user_id=item.get("user_id"),
            revoked=bool(item.get("revoked", False)),
            expires_at=_parse_expires_at(item.get("expires_at")),
            previous_key_hashes=previous_hashes,
        )
    return registry


def route_permission(method: str, path: str) -> str | None:
    permission = PERMISSION_BY_ROUTE.get((method, path))
    if permission:
        return permission
    for expected_method, prefix, dynamic_permission in DYNAMIC_PREFIX_PERMISSIONS:
        if method == expected_method and path.startswith(prefix):
            return dynamic_permission
    return None


def authenticate_request(request: Request, registry: IdentityRegistry) -> TenantContext | None:
    return registry.authenticate(request.headers.get("X-API-Key"), request.headers.get("X-Tenant-ID"))


def require_tenant_context(request: Request) -> TenantContext:
    context = getattr(request.state, "tenant_context", None)
    if context is None:
        raise RuntimeError("tenant context is required")
    return context


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


def is_public_path(path: str) -> bool:
    return path in public_paths() or path.startswith("/architecture/levels/")


def public_paths() -> set[str]:
    return {
        "/",
        "/health",
        "/live",
        "/ready",
        "/metrics",
        "/security/policy",
        "/architecture/levels",
        "/architecture/readiness",
        "/architecture/competitive-advantages",
        "/tools",
        "/mcp/manifest",
        "/docs",
        "/openapi.json",
        "/redoc",
    }


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
