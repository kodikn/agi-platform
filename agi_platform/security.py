from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from agi_platform.outbound import validate_outbound_url as _validate_outbound_url

if TYPE_CHECKING:
    from fastapi import Request


PERMISSIONS = {
    "memory.read",
    "memory.write",
    "memory.delete",
    "workflow.read",
    "workflow.start",
    "workflow.cancel",
    "github.read",
    "github.index",
    "graph.read",
    "graph.write",
    "sandbox.execute",
    "governance.propose",
    "governance.review",
    "governance.approve",
    "evolution.propose",
    "evolution.approve",
    "evolution.deploy",
    "production.mutate",
}

LEGACY_PERMISSION_MAP = {
    "memory:read": "memory.read",
    "memory:write": "memory.write",
    "workflow:create": "workflow.start",
    "workflow:execute": "workflow.start",
    "github:read": "github.read",
    "github:index": "github.index",
    "graph:read": "graph.read",
    "graph:write": "graph.write",
    "sandbox:execute": "sandbox.execute",
    "governance:propose": "governance.propose",
    "governance:approve": "governance.approve",
    "evolution:propose": "evolution.propose",
}

HIGH_RISK_ACTIONS = {
    "sandbox.execute",
    "evolution.deploy",
    "production.mutate",
    "governance.approve",
}

GOVERNANCE_ACTIONS = {
    "governance.propose",
    "governance.review",
    "governance.approve",
}


def normalize_permission(permission: str) -> str:
    return LEGACY_PERMISSION_MAP.get(permission, permission)


@dataclass(frozen=True)
class Identity:
    subject: str
    tenant_id: str
    roles: frozenset[str]
    permissions: frozenset[str]
    key_id: str = ""
    identity_type: str = "service_account"

    def can(self, permission: str) -> bool:
        normalized = normalize_permission(permission)
        return "*" in self.permissions or normalized in self.permissions


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    identity: Identity
    request_id: str


@dataclass(frozen=True)
class APIKeyRecord:
    key_hash: str
    subject: str
    tenant_id: str
    roles: frozenset[str]
    permissions: frozenset[str]
    key_id: str
    revoked: bool = False
    expires_at: int | None = None
    scopes: frozenset[str] = frozenset()

    def active(self, now: int | None = None) -> bool:
        now = int(time.time()) if now is None else now
        return not self.revoked and (
            self.expires_at is None or self.expires_at > now
        )


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    audit_required: bool = False


@dataclass
class AuditTrail:
    events: list[dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        tenant_id: str,
        subject: str,
        action: str,
        resource: str,
        result: str,
        reason: str,
        request_id: str = "",
    ) -> None:
        self.events.append(
            {
                "tenant_id": tenant_id,
                "subject": subject,
                "action": action,
                "resource": resource,
                "result": result,
                "reason": reason,
                "request_id": request_id,
                "created_at": int(time.time()),
            }
        )


class PolicyEngine:
    def __init__(self, audit: AuditTrail | None = None) -> None:
        self.audit = audit or AuditTrail()

    def authorize(
        self,
        subject: Identity | None,
        tenant: TenantContext | None,
        action: str,
        resource: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> AuthorizationDecision:
        action = normalize_permission(action)
        resource = resource or {}
        context = context or {}

        if (
            subject is None
            or tenant is None
            or subject.tenant_id != tenant.tenant_id
        ):
            return AuthorizationDecision(
                False,
                "missing_or_cross_tenant_context",
            )

        if action not in PERMISSIONS:
            return AuthorizationDecision(False, "unknown_action")

        resource_tenant = resource.get(
            "tenant_id",
            tenant.tenant_id,
        )

        if resource_tenant != tenant.tenant_id:
            return AuthorizationDecision(
                False,
                "resource_tenant_mismatch",
                action in GOVERNANCE_ACTIONS,
            )

        if not subject.can(action):
            return AuthorizationDecision(
                False,
                "missing_permission",
                action in GOVERNANCE_ACTIONS,
            )

        if action in HIGH_RISK_ACTIONS and not context.get("approved"):
            return AuthorizationDecision(
                False,
                "approval_required",
                action in GOVERNANCE_ACTIONS,
            )

        return AuthorizationDecision(
            True,
            "allowed",
            action in GOVERNANCE_ACTIONS,
        )


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    plaintext = f"agi_{secrets.token_urlsafe(32)}"
    return plaintext, hash_api_key(plaintext)


PERMISSION_BY_ROUTE = {
    ("POST", "/memory/store"): "memory.write",
    ("POST", "/memory/search"): "memory.read",
    ("POST", "/memory/retrieve"): "memory.read",
    ("POST", "/memory/consolidate"): "memory.write",
    ("POST", "/guardian/validate"): "memory.write",
    ("POST", "/github/repositories"): "github.index",
    ("POST", "/sandbox/execute"): "sandbox.execute",
    ("POST", "/graph/entities"): "graph.write",
    ("POST", "/graph/relationships"): "graph.write",
    ("POST", "/graph/search"): "graph.read",
    ("POST", "/orchestrate"): "workflow.start",
    ("POST", "/governance/proposals"): "governance.propose",
    ("POST", "/governance/reviews"): "governance.approve",
    ("POST", "/evolution/evaluate"): "evolution.propose",
    ("POST", "/evolution/proposals"): "evolution.propose",
}

DYNAMIC_PREFIX_PERMISSIONS = (
    ("GET", "/github/repositories/", "github.read"),
    ("POST", "/orchestrate/", "workflow.start"),
)


@dataclass
class RateLimiter:
    limit_per_minute: int
    windows: dict[str, deque[float]] = field(
        default_factory=lambda: defaultdict(deque)
    )

    def allow(self, identity: str) -> bool:
        now = time.time()
        window = self.windows[identity]

        while window and now - window[0] >= 60:
            window.popleft()

        if len(window) >= self.limit_per_minute:
            return False

        window.append(now)
        return True


def parse_api_keys(
    raw: str | None,
    legacy_key: str | None,
) -> dict[str, APIKeyRecord]:
    records: dict[str, APIKeyRecord] = {}

    if raw:
        data = json.loads(raw)

        if not isinstance(data, list):
            raise ValueError("AGI_API_KEYS must be a JSON list")

        for index, item in enumerate(data):
            plaintext = item.get("key")

            key_hash = str(
                item.get("key_hash")
                or hash_api_key(str(plaintext))
            )

            if not key_hash or key_hash == hash_api_key("None"):
                raise ValueError(
                    "API keys require key_hash or bootstrap key"
                )

            perms = frozenset(
                normalize_permission(str(p))
                for p in item.get("permissions", [])
            )

            record = APIKeyRecord(
                key_hash,
                str(
                    item.get("subject")
                    or f"service-account-{index}"
                ),
                str(item["tenant_id"]),
                frozenset(item.get("roles", ["service"])),
                perms,
                str(
                    item.get("key_id")
                    or f"key-{index}"
                ),
                bool(item.get("revoked", False)),
                item.get("expires_at"),
                frozenset(item.get("scopes", [])),
            )

            records[key_hash] = record

    if legacy_key:
        records.setdefault(
            hash_api_key(legacy_key),
            APIKeyRecord(
                hash_api_key(legacy_key),
                "legacy-api-key",
                "legacy",
                frozenset({"admin"}),
                frozenset({"*"}),
                "legacy",
            ),
        )

    return records


def route_permission(
    method: str,
    path: str,
) -> str | None:
    if (method, path) in PERMISSION_BY_ROUTE:
        return PERMISSION_BY_ROUTE[(method, path)]

    for m, prefix, permission in DYNAMIC_PREFIX_PERMISSIONS:
        if method == m and path.startswith(prefix):
            return permission

    return None


def authenticate_request(
    request: Request,
    api_keys: dict[str, APIKeyRecord],
) -> Identity | None:
    raw_key = request.headers.get("X-API-Key")

    if not raw_key:
        return None

    record = api_keys.get(hash_api_key(raw_key))

    if not record or not record.active():
        return None

    tenant_header = request.headers.get("X-Tenant-ID")

    if tenant_header and not hmac.compare_digest(
        tenant_header,
        record.tenant_id,
    ):
        return None

    return Identity(
        record.subject,
        record.tenant_id,
        record.roles,
        record.permissions,
        record.key_id,
    )


def canonical_error(
    code: str,
    message: str,
    request_id: str,
    status_code: int,
):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
    )


def security_headers() -> dict[str, str]:
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": (
            "geolocation=(), microphone=(), camera=()"
        ),
        "Cache-Control": "no-store",
    }


def apply_production_headers(
    response,
    service_name: str,
):
    for key, value in security_headers().items():
        response.headers[key] = value

    response.headers["X-Service-Name"] = service_name

    return response


def is_public_path(path: str) -> bool:
    return path in public_paths() or path.startswith(
        "/architecture/levels/"
    )


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


def validate_outbound_url(url: str) -> str:
    return _validate_outbound_url(url)


def request_id() -> str:
    return uuid.uuid4().hex