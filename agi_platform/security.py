from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

import redis
from redis.exceptions import RedisError

from agi_platform.outbound import validate_outbound_url as _validate_outbound_url

if TYPE_CHECKING:
    from fastapi import Request

logger = logging.getLogger(__name__)


class PlatformError(Exception):
    code = "internal_error"
    status_code = 500
    safe_message = "Request could not be completed."

    def __init__(self, message: str | None = None, *, safe_message: str | None = None) -> None:
        super().__init__(message or safe_message or self.safe_message)
        self.message = message or self.safe_message
        if safe_message is not None:
            self.safe_message = safe_message


class AuthenticationError(PlatformError):
    code = "unauthenticated"; status_code = 401; safe_message = "Valid authentication is required."
class AuthorizationError(PlatformError):
    code = "forbidden"; status_code = 403; safe_message = "Permission denied."
class ValidationError(PlatformError):
    code = "invalid_request"; status_code = 422; safe_message = "Request validation failed."
class NotFoundError(PlatformError):
    code = "not_found"; status_code = 404; safe_message = "Resource not found."
class ConflictError(PlatformError):
    code = "conflict"; status_code = 409; safe_message = "Resource conflict."
class DependencyError(PlatformError):
    code = "dependency_unavailable"; status_code = 503; safe_message = "Required dependency is unavailable."
class ProviderError(PlatformError):
    code = "provider_unavailable"; status_code = 503; safe_message = "Provider unavailable."
class RateLimitError(PlatformError):
    code = "rate_limited"; status_code = 429; safe_message = "Rate limit exceeded."
class SandboxError(PlatformError):
    code = "sandbox_error"; status_code = 403; safe_message = "Sandbox operation denied."
class PolicyDeniedError(PlatformError):
    code = "policy_denied"; status_code = 403; safe_message = "Policy denied the request."
class InternalError(PlatformError):
    code = "internal_error"; status_code = 500; safe_message = "Request could not be completed."


PERMISSIONS = {
    "memory.read", "memory.write", "memory.delete", "workflow.read", "workflow.start", "workflow.cancel", "github.read", "github.index", "graph.read", "graph.write", "sandbox.execute", "governance.propose", "governance.review", "governance.approve", "evolution.propose", "evolution.approve", "evolution.deploy", "production.mutate",
}
LEGACY_PERMISSION_MAP = {"memory:read":"memory.read","memory:write":"memory.write","workflow:create":"workflow.start","workflow:execute":"workflow.start","github:read":"github.read","github:index":"github.index","graph:read":"graph.read","graph:write":"graph.write","sandbox:execute":"sandbox.execute","governance:propose":"governance.propose","governance:approve":"governance.approve","evolution:propose":"evolution.propose"}
HIGH_RISK_ACTIONS = {"sandbox.execute", "evolution.deploy", "production.mutate", "governance.approve"}
GOVERNANCE_ACTIONS = {"governance.propose", "governance.review", "governance.approve"}
EXPENSIVE_OPERATIONS = {"llm", "sandbox", "embeddings", "research", "github_indexing"}


def normalize_permission(permission: str) -> str:
    return LEGACY_PERMISSION_MAP.get(permission, permission)


@dataclass(frozen=True)
class Identity:
    subject: str; tenant_id: str; roles: frozenset[str]; permissions: frozenset[str]; key_id: str = ""; identity_type: str = "service_account"
    def can(self, permission: str) -> bool:
        normalized = normalize_permission(permission)
        return "*" in self.permissions or normalized in self.permissions

@dataclass(frozen=True)
class TenantContext:
    tenant_id: str; identity: Identity; request_id: str

@dataclass(frozen=True)
class APIKeyRecord:
    key_hash: str; subject: str; tenant_id: str; roles: frozenset[str]; permissions: frozenset[str]; key_id: str; revoked: bool = False; expires_at: int | None = None; scopes: frozenset[str] = frozenset()
    def active(self, now: int | None = None) -> bool:
        now = int(time.time()) if now is None else now
        return not self.revoked and (self.expires_at is None or self.expires_at > now)

@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool; reason: str; audit_required: bool = False

@dataclass
class AuditTrail:
    events: list[dict[str, Any]] = field(default_factory=list)
    def record(self, tenant_id: str, subject: str, action: str, resource: str, result: str, reason: str, request_id: str = "") -> None:
        self.events.append({"tenant_id": tenant_id, "subject": subject, "action": action, "resource": resource, "result": result, "reason": reason, "request_id": request_id, "created_at": int(time.time())})

class PolicyEngine:
    def __init__(self, audit: AuditTrail | None = None) -> None: self.audit = audit or AuditTrail()
    def authorize(self, subject: Identity | None, tenant: TenantContext | None, action: str, resource: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> AuthorizationDecision:
        action = normalize_permission(action); resource = resource or {}; context = context or {}
        if subject is None or tenant is None or subject.tenant_id != tenant.tenant_id: return AuthorizationDecision(False, "missing_or_cross_tenant_context")
        if action not in PERMISSIONS: return AuthorizationDecision(False, "unknown_action")
        if resource.get("tenant_id", tenant.tenant_id) != tenant.tenant_id: return AuthorizationDecision(False, "resource_tenant_mismatch", action in GOVERNANCE_ACTIONS)
        if not subject.can(action): return AuthorizationDecision(False, "missing_permission", action in GOVERNANCE_ACTIONS)
        if action in HIGH_RISK_ACTIONS and not context.get("approved"): return AuthorizationDecision(False, "approval_required", action in GOVERNANCE_ACTIONS)
        return AuthorizationDecision(True, "allowed", action in GOVERNANCE_ACTIONS)


def hash_api_key(key: str) -> str: return hashlib.sha256(key.encode()).hexdigest()
def generate_api_key() -> tuple[str, str]:
    plaintext = f"agi_{secrets.token_urlsafe(32)}"; return plaintext, hash_api_key(plaintext)

PERMISSION_BY_ROUTE = {("POST", "/memory/store"): "memory.write", ("POST", "/memory/search"): "memory.read", ("POST", "/memory/retrieve"): "memory.read", ("POST", "/memory/consolidate"): "memory.write", ("POST", "/guardian/validate"): "memory.write", ("POST", "/github/repositories"): "github.index", ("POST", "/sandbox/execute"): "sandbox.execute", ("POST", "/graph/entities"): "graph.write", ("POST", "/graph/relationships"): "graph.write", ("POST", "/graph/search"): "graph.read", ("POST", "/orchestrate"): "workflow.start", ("POST", "/governance/proposals"): "governance.propose", ("POST", "/governance/reviews"): "governance.approve", ("POST", "/evolution/evaluate"): "evolution.propose", ("POST", "/evolution/proposals"): "evolution.propose"}
DYNAMIC_PREFIX_PERMISSIONS = (("GET", "/github/repositories/", "github.read"), ("POST", "/orchestrate/", "workflow.start"))

@dataclass(frozen=True)
class RateLimitRule:
    scope: str; limit: int; window_seconds: int = 60; fail_closed: bool = True

class RedisRateLimiter:
    def __init__(self, redis_url: str, default_limit_per_minute: int, *, client: Any | None = None, enabled: bool = True) -> None:
        self.client = client or redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=0.25, socket_timeout=0.25)
        self.enabled = enabled
        self.default_limit = default_limit_per_minute
    def check(self, rules: list[RateLimitRule], request_id: str) -> None:
        if not self.enabled: return
        try:
            pipe = self.client.pipeline()
            keys = []
            now_bucket = int(time.time())
            for rule in rules:
                bucket = now_bucket // rule.window_seconds
                key = f"rl:{rule.scope}:{bucket}"
                keys.append((key, rule))
                pipe.incr(key); pipe.expire(key, rule.window_seconds + 5)
            values = pipe.execute()[0::2]
        except RedisError as exc:
            logger.warning("redis_rate_limit_unavailable", extra={"request_id": request_id, "error": repr(exc)})
            if any(rule.fail_closed for rule in rules):
                raise DependencyError("Redis unavailable for security-sensitive rate limit", safe_message="Rate limit dependency unavailable.") from exc
            return
        for count, (_key, rule) in zip(values, keys):
            if int(count) > rule.limit:
                raise RateLimitError(f"rate limit exceeded for {rule.scope}")

class RateLimiter:
    """Compatibility shim: local limiter only for explicit development fallback, not production."""
    def __init__(self, limit_per_minute: int):
        self.limit_per_minute = limit_per_minute; self.windows: dict[str, deque[float]] = defaultdict(deque)
    def allow(self, identity: str) -> bool:
        now = time.time(); window = self.windows[identity]
        while window and now - window[0] >= 60: window.popleft()
        if len(window) >= self.limit_per_minute: return False
        window.append(now); return True

@dataclass(frozen=True)
class LockHandle:
    name: str; owner: str; ttl_ms: int

class RedisDistributedLock:
    RELEASE_SCRIPT = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
      return redis.call('del', KEYS[1])
    end
    return 0
    """
    def __init__(self, redis_url: str, *, client: Any | None = None) -> None:
        self.client = client or redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=0.25, socket_timeout=0.25)
    def acquire(self, name: str, *, ttl_ms: int = 30000, timeout_ms: int = 5000, retry_ms: int = 100, owner: str | None = None) -> LockHandle:
        owner = owner or uuid.uuid4().hex; key = f"lock:{name}"; deadline = time.monotonic() + timeout_ms / 1000
        while True:
            try:
                if self.client.set(key, owner, nx=True, px=ttl_ms): return LockHandle(name, owner, ttl_ms)
            except RedisError as exc:
                raise DependencyError("Redis unavailable for distributed lock", safe_message="Lock dependency unavailable.") from exc
            if time.monotonic() >= deadline: raise ConflictError(f"lock timeout: {name}", safe_message="Operation is already in progress.")
            time.sleep(retry_ms / 1000)
    def release(self, handle: LockHandle) -> bool:
        try:
            return bool(self.client.eval(self.RELEASE_SCRIPT, 1, f"lock:{handle.name}", handle.owner))
        except RedisError as exc:
            raise DependencyError("Redis unavailable while releasing distributed lock", safe_message="Lock dependency unavailable.") from exc
    def run_once(self, name: str, fn: Callable[[], Any], **kwargs: Any) -> Any:
        handle = self.acquire(name, **kwargs)
        try: return fn()
        finally: self.release(handle)


def parse_api_keys(raw: str | None, legacy_key: str | None) -> dict[str, APIKeyRecord]:
    records: dict[str, APIKeyRecord] = {}
    if raw:
        data = json.loads(raw)
        if not isinstance(data, list): raise ValueError("AGI_API_KEYS must be a JSON list")
        for index, item in enumerate(data):
            plaintext = item.get("key"); key_hash = str(item.get("key_hash") or hash_api_key(str(plaintext)))
            if not key_hash or key_hash == hash_api_key("None"): raise ValueError("API keys require key_hash or bootstrap key")
            perms = frozenset(normalize_permission(str(p)) for p in item.get("permissions", []))
            records[key_hash] = APIKeyRecord(key_hash, str(item.get("subject") or f"service-account-{index}"), str(item["tenant_id"]), frozenset(item.get("roles", ["service"])), perms, str(item.get("key_id") or f"key-{index}"), bool(item.get("revoked", False)), item.get("expires_at"), frozenset(item.get("scopes", [])))
    if legacy_key:
        records.setdefault(hash_api_key(legacy_key), APIKeyRecord(hash_api_key(legacy_key), "legacy-api-key", "legacy", frozenset({"admin"}), frozenset({"*"}), "legacy"))
    return records

def route_permission(method: str, path: str) -> str | None:
    if (method, path) in PERMISSION_BY_ROUTE: return PERMISSION_BY_ROUTE[(method, path)]
    for m, prefix, permission in DYNAMIC_PREFIX_PERMISSIONS:
        if method == m and path.startswith(prefix): return permission
    return None

def authenticate_request(request: Request, api_keys: dict[str, APIKeyRecord]) -> Identity | None:
    raw_key = request.headers.get("X-API-Key")
    if not raw_key: return None
    record = api_keys.get(hash_api_key(raw_key))
    if not record or not record.active(): return None
    tenant_header = request.headers.get("X-Tenant-ID")
    if tenant_header and not hmac.compare_digest(tenant_header, record.tenant_id): return None
    return Identity(record.subject, record.tenant_id, record.roles, record.permissions, record.key_id)

def canonical_error(code: str, message: str, request_id: str, status_code: int):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "request_id": request_id}})

def security_headers() -> dict[str, str]:
    return {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Permissions-Policy": "geolocation=(), microphone=(), camera=()", "Cache-Control": "no-store"}

def apply_production_headers(response, service_name: str):
    for key, value in security_headers().items(): response.headers[key] = value
    response.headers["X-Service-Name"] = service_name
    return response

def is_public_path(path: str) -> bool: return path in public_paths() or path.startswith("/architecture/levels/")
def public_paths() -> set[str]:
    return {"/", "/health", "/live", "/ready", "/metrics", "/security/policy", "/architecture/levels", "/architecture/readiness", "/architecture/competitive-advantages", "/tools", "/mcp/manifest", "/docs", "/openapi.json", "/redoc"}
def validate_outbound_url(url: str) -> str: return _validate_outbound_url(url)
def request_id() -> str: return uuid.uuid4().hex
