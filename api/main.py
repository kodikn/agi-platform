import logging
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from agi_platform.config import settings
from agi_platform.readiness import platform_ready
from agi_platform.telemetry import configure_json_logging, trace_id
from agi_platform.security import (
    RedisRateLimiter,
    RateLimitRule,
    PlatformError,
    AuthorizationError,
    NotFoundError,
    ProviderError,
    SandboxError,
    apply_production_headers,
    AuditTrail,
    PolicyEngine,
    TenantContext,
    authenticate_request,
    canonical_error,
    parse_api_keys,
    is_public_path,
    public_paths,
    request_id,
    route_permission,
)
from agi_platform.services import (
    ChatRequest,
    ChineseArticleRequest,
    EmbeddingRequest,
    EntityRequest,
    EvaluationRequest,
    GovernanceProposalRequest,
    GovernanceReviewRequest,
    MemoryRequest,
    PlatformService,
    QueryRequest,
    RelationshipRequest,
    RepositoryRequest,
    SandboxRequest,
    WorkflowRequest,
)

configure_json_logging()
app = FastAPI(title="AGI Platform", version="0.3.0")
service = PlatformService()
logger = logging.getLogger(__name__)
rate_limiter = RedisRateLimiter(
    settings.redis_url, settings.rate_limit_per_minute, enabled=settings.redis_required
)
api_keys = parse_api_keys(getattr(settings, "api_keys", None), settings.api_key)
audit_trail = AuditTrail()
policy_engine = PolicyEngine(audit_trail)


def tenant_context(request: Request) -> TenantContext:
    context = getattr(request.state, "tenant_context", None)
    if context is None:
        raise AuthorizationError("Tenant context required.")
    return context


@app.middleware("http")
async def production_controls(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or request_id()
    tid = (
        request.headers.get("traceparent", "").split("-")[1]
        if request.headers.get("traceparent", "").startswith("00-")
        else trace_id()
    )
    request.state.request_id = rid
    request.state.trace_id = tid
    client_ip = request.client.host if request.client else "unknown"
    raw_key = request.headers.get("X-API-Key") or "anonymous"
    tenant_header = request.headers.get("X-Tenant-ID") or "unknown"
    rate_rules = [
        RateLimitRule(
            f"ip:{client_ip}",
            settings.rate_limit_per_minute,
            fail_closed=not settings.rate_limit_fail_open,
        ),
        RateLimitRule(
            f"api_key:{raw_key}",
            settings.rate_limit_per_minute,
            fail_closed=not settings.rate_limit_fail_open,
        ),
        RateLimitRule(
            f"tenant:{tenant_header}",
            settings.rate_limit_per_minute * 5,
            fail_closed=not settings.rate_limit_fail_open,
        ),
    ]
    expensive = {
        "/chat": "llm",
        "/completion": "llm",
        "/embeddings": "embeddings",
        "/research/query": "research",
        "/research/report": "research",
        "/sandbox/execute": "sandbox",
        "/github/repositories": "github_indexing",
    }.get(request.url.path)
    if expensive:
        rate_rules.append(
            RateLimitRule(
                f"expensive:{expensive}",
                max(1, settings.rate_limit_per_minute // 4),
                fail_closed=True,
            )
        )
    try:
        rate_limiter.check(rate_rules, rid)
    except PlatformError as exc:
        logger.warning(
            "rate_limit_error",
            extra={
                "request_id": rid,
                "code": exc.code,
                "internal_message": exc.message,
            },
        )
        response = canonical_error(exc.code, exc.safe_message, rid, exc.status_code)
        response.headers["X-Request-ID"] = rid
        return apply_production_headers(response, settings.service_name)

    if not is_public_path(request.url.path):
        permission = route_permission(request.method, request.url.path)
        if api_keys:
            identity = authenticate_request(request, api_keys)
            if identity is None:
                response = canonical_error(
                    "unauthenticated", "Valid API key required.", rid, 401
                )
                response.headers["X-Request-ID"] = rid
                return apply_production_headers(response, settings.service_name)
            request.state.identity = identity
            request.state.tenant_id = identity.tenant_id
            request.state.tenant_context = TenantContext(
                identity.tenant_id, identity, rid
            )
            if permission:
                decision = policy_engine.authorize(
                    identity,
                    request.state.tenant_context,
                    permission,
                    {"tenant_id": identity.tenant_id},
                    {"approved": request.headers.get("X-Approval-ID") is not None},
                )
                if decision.audit_required:
                    audit_trail.record(
                        identity.tenant_id,
                        identity.subject,
                        permission,
                        request.url.path,
                        "allowed" if decision.allowed else "denied",
                        decision.reason,
                        rid,
                    )
                if not decision.allowed:
                    logger.info(
                        "authorization_denied",
                        extra={"request_id": rid, "reason": decision.reason},
                    )
                    response = canonical_error(
                        "forbidden", "Permission denied.", rid, 403
                    )
                    response.headers["X-Request-ID"] = rid
                    return apply_production_headers(response, settings.service_name)
        elif permission and request.url.path.startswith(
            (
                "/sandbox",
                "/orchestrate",
                "/github",
                "/graph",
                "/governance",
                "/evolution",
            )
        ):
            response = canonical_error(
                "dependency_unavailable",
                "Authorization must be configured for this endpoint.",
                rid,
                503,
            )
            response.headers["X-Request-ID"] = rid
            return apply_production_headers(response, settings.service_name)

    started = time.perf_counter()
    response = await call_next(request)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    tenant_id = getattr(request.state, "tenant_id", "anonymous")
    actor_id = getattr(getattr(request.state, "identity", None), "subject", "anonymous")
    service.telemetry.increment(
        "http_requests_total",
        method=request.method,
        path=request.url.path,
        status=str(response.status_code),
    )
    service.telemetry.observe(
        "http_request_latency_ms",
        latency_ms,
        method=request.method,
        path=request.url.path,
    )
    if response.status_code >= 400:
        service.telemetry.increment(
            "http_errors_total",
            method=request.method,
            path=request.url.path,
            status=str(response.status_code),
        )
    logger.info(
        "http_request",
        extra={
            "request_id": rid,
            "trace_id": tid,
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
        },
    )
    response.headers["X-Request-ID"] = rid
    response.headers["Trace-ID"] = tid
    return apply_production_headers(response, settings.service_name)


@app.exception_handler(PlatformError)
async def platform_exception_handler(request: Request, exc: PlatformError):
    rid = getattr(request.state, "request_id", request_id())
    logger.info(
        "platform_error",
        extra={"request_id": rid, "code": exc.code, "internal_message": exc.message},
    )
    response = canonical_error(exc.code, exc.safe_message, rid, exc.status_code)
    response.headers["X-Request-ID"] = rid
    response.headers["Trace-ID"] = getattr(request.state, "trace_id", trace_id())
    return apply_production_headers(response, settings.service_name)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    rid = getattr(request.state, "request_id", request_id())
    code_by_status = {
        401: "unauthenticated",
        403: "forbidden",
        404: "not_found",
        422: "invalid_request",
        503: "service_unavailable",
    }
    message = (
        exc.detail
        if isinstance(exc.detail, str)
        and (exc.status_code < 500 or exc.status_code == 503)
        else "Request could not be completed."
    )
    response = canonical_error(
        code_by_status.get(exc.status_code, "request_error"),
        message,
        rid,
        exc.status_code,
    )
    response.headers["X-Request-ID"] = rid
    return apply_production_headers(response, settings.service_name)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", request_id())
    logger.exception("unhandled_api_error", extra={"request_id": rid})
    response = canonical_error(
        "internal_error", "Request could not be completed.", rid, 500
    )
    response.headers["X-Request-ID"] = rid
    return apply_production_headers(response, settings.service_name)


class CodeAnalysisRequest(BaseModel):
    code: str = Field(min_length=1)


@app.get("/")
def root():
    return service.health()


@app.get("/health")
def health():
    return service.health()


@app.get("/live")
def live():
    return {"status": "alive", "service": settings.service_name}


@app.get("/ready")
def ready():
    return platform_ready()


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return service.telemetry.prometheus()


@app.get("/security/policy")
def security_policy():
    return {
        "api_key_required": bool(settings.api_key),
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "public_paths": sorted(public_paths()),
    }


@app.get("/architecture/levels")
def levels():
    return service.levels()


@app.get("/architecture/readiness")
def architecture_readiness():
    return platform_ready()["levels"]


@app.get("/architecture/competitive-advantages")
def architecture_competitive_advantages():
    return service.competitive_advantages()


@app.get("/tools")
def tools():
    return service.tools()


@app.get("/mcp/manifest")
def mcp_manifest():
    return service.mcp_manifest()


@app.get("/architecture/levels/{level}")
def level(level: int):
    try:
        return service.level(level)
    except KeyError as exc:
        raise NotFoundError("architecture level lookup failed") from exc


@app.post("/chat")
def chat(request: ChatRequest):
    try:
        return service.chat(request)
    except Exception as exc:
        raise ProviderError("LLM provider unavailable") from exc


@app.post("/completion")
def completion(request: ChatRequest):
    try:
        return service.chat(request)
    except Exception as exc:
        raise ProviderError("LLM provider unavailable") from exc


@app.post("/embeddings")
def embeddings(request: EmbeddingRequest):
    try:
        return service.embeddings(request)
    except Exception as exc:
        raise ProviderError("LLM provider unavailable") from exc


@app.get("/models")
def models():
    return service.llm.models()


@app.post("/memory/store")
def memory_store(
    request: MemoryRequest, context: TenantContext = Depends(tenant_context)
):
    return service.store_memory(request, context)


@app.post("/memory/search")
def memory_search(
    request: QueryRequest, context: TenantContext = Depends(tenant_context)
):
    return service.search_memory(request, context)


@app.post("/memory/retrieve")
def memory_retrieve(
    request: QueryRequest, context: TenantContext = Depends(tenant_context)
):
    return service.search_memory(request, context)


@app.post("/memory/consolidate")
def memory_consolidate(context: TenantContext = Depends(tenant_context)):
    return service.memory.consolidate(context)


@app.post("/guardian/validate")
def guardian_validate(
    request: MemoryRequest, context: TenantContext = Depends(tenant_context)
):
    return service.validate_memory(request, context)


@app.get("/guardian/audit")
def guardian_audit():
    return {"audit": service.guardian.audit, "reviews": service.guardian.reviews}


@app.post("/research/query")
def research_query(request: QueryRequest):
    return service.research.query(request.query)


@app.post("/research/report")
def research_report(request: QueryRequest):
    return service.research_report(request)


@app.post("/chinese/articles")
def chinese_articles(request: ChineseArticleRequest):
    return service.chinese_hub.ingest(request.title, request.body, request.script)


@app.post("/chinese/analyze")
def chinese_analyze(request: ChineseArticleRequest):
    return service.chinese_hub.ingest(request.title, request.body, request.script)


@app.post("/analyze/code")
def analyze_code(request: CodeAnalysisRequest):
    return service.analyze_code(request.code)


@app.post("/analyze/repository")
def analyze_repository(files: dict[str, str]):
    return service.analysis.analyze_repository(files)


@app.post("/github/repositories")
def github_repository(request: RepositoryRequest):
    try:
        return service.github.index_repository(request.url, request.dependencies)
    except ValueError as exc:
        raise SandboxError(
            "Invalid repository URL", safe_message="Invalid repository URL"
        ) from exc
    except Exception as exc:
        raise ProviderError("GitHub provider unavailable") from exc


@app.get("/github/repositories/{owner}/{repo}")
def github_analyze(owner: str, repo: str):
    try:
        return service.github.analyze(f"{owner}/{repo}")
    except KeyError as exc:
        raise NotFoundError("architecture level lookup failed") from exc


@app.post("/sandbox/execute")
def sandbox_execute(request: SandboxRequest):
    try:
        return service.sandbox.execute(request.command, request.timeout_seconds)
    except ValueError as exc:
        raise SandboxError("Sandbox command denied") from exc


@app.post("/graph/entities")
def graph_entity(
    request: EntityRequest, context: TenantContext = Depends(tenant_context)
):
    return service.graph.upsert_entity(
        context, request.entity_id, request.labels, request.properties
    )


@app.post("/graph/relationships")
def graph_relationship(
    request: RelationshipRequest, context: TenantContext = Depends(tenant_context)
):
    try:
        return service.graph.relate(
            context,
            request.source,
            request.target,
            request.relationship,
            request.properties,
        )
    except KeyError as exc:
        raise NotFoundError("architecture level lookup failed") from exc


@app.post("/graph/search")
def graph_search(
    request: QueryRequest, context: TenantContext = Depends(tenant_context)
):
    return service.graph.search(context, request.query)


@app.post("/orchestrate")
def orchestrate(request: WorkflowRequest):
    return service.workflow.plan(request.task, request.agents or None)


@app.post("/orchestrate/{checkpoint}/execute")
def orchestrate_execute(checkpoint: str):
    try:
        return service.workflow.execute(checkpoint)
    except KeyError as exc:
        raise NotFoundError("architecture level lookup failed") from exc


@app.post("/orchestrate/{checkpoint}/recover")
def orchestrate_recover(checkpoint: str):
    try:
        return service.workflow.recover(checkpoint)
    except KeyError as exc:
        raise NotFoundError("architecture level lookup failed") from exc


@app.post("/governance/proposals")
def governance_proposals(request: GovernanceProposalRequest):
    return service.governance.propose(request.title, request.body, request.risk_score)


@app.post("/governance/reviews")
def governance_reviews(request: GovernanceReviewRequest):
    return service.governance.review(
        request.decision_id, request.approver, request.approved
    )


@app.post("/evolution/evaluate")
def evolution_evaluate(request: EvaluationRequest):
    return service.evolution.evaluate(request.metrics)


@app.post("/evolution/proposals")
def evolution_proposals():
    return service.improvement_proposals()
