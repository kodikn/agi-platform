from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from agi_platform.config import settings
from agi_platform.readiness import platform_ready
from agi_platform.security import (
    RateLimiter,
    apply_production_headers,
    authenticate_request,
    canonical_error,
    parse_api_keys,
    is_public_path,
    require_tenant_context,
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

app = FastAPI(title="AGI Platform", version="0.3.0")
service = PlatformService()
rate_limiter = RateLimiter(settings.rate_limit_per_minute)
identity_registry = parse_api_keys(getattr(settings, "api_keys", None), settings.api_key)


@app.middleware("http")
async def production_controls(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or request_id()
    request.state.request_id = rid
    identity_key = request.headers.get("X-API-Key") or (request.client.host if request.client else "unknown")
    if not rate_limiter.allow(identity_key):
        response = canonical_error("rate_limited", "Rate limit exceeded.", rid, 429)
        response.headers["X-Request-ID"] = rid
        return apply_production_headers(response, settings.service_name)

    if not is_public_path(request.url.path):
        permission = route_permission(request.method, request.url.path)
        if identity_registry.api_keys:
            identity = authenticate_request(request, identity_registry)
            if identity is None:
                response = canonical_error("unauthenticated", "Valid API key required.", rid, 401)
                response.headers["X-Request-ID"] = rid
                return apply_production_headers(response, settings.service_name)
            request.state.identity = identity
            request.state.tenant_context = identity
            request.state.tenant_id = identity.tenant_id
            if permission and not identity.can(permission):
                response = canonical_error("forbidden", "Permission denied.", rid, 403)
                response.headers["X-Request-ID"] = rid
                return apply_production_headers(response, settings.service_name)
        elif permission and request.url.path.startswith(("/sandbox", "/orchestrate", "/github", "/graph", "/governance", "/evolution")):
            response = canonical_error("auth_not_configured", "Authorization must be configured for this endpoint.", rid, 503)
            response.headers["X-Request-ID"] = rid
            return apply_production_headers(response, settings.service_name)

    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return apply_production_headers(response, settings.service_name)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    rid = getattr(request.state, "request_id", request_id())
    code_by_status = {401: "unauthenticated", 403: "forbidden", 404: "not_found", 422: "invalid_request", 503: "service_unavailable"}
    message = exc.detail if isinstance(exc.detail, str) and (exc.status_code < 500 or exc.status_code == 503) else "Request could not be completed."
    response = canonical_error(code_by_status.get(exc.status_code, "request_error"), message, rid, exc.status_code)
    response.headers["X-Request-ID"] = rid
    return apply_production_headers(response, settings.service_name)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", request_id())
    response = canonical_error("internal_error", "Request could not be completed.", rid, 500)
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
    return {"api_key_required": bool(identity_registry.api_keys), "rate_limit_per_minute": settings.rate_limit_per_minute, "public_paths": sorted(public_paths())}


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
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/chat")
def chat(request: Request, payload: ChatRequest):
    try:
        return service.chat(payload, require_tenant_context(request))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="LLM provider unavailable") from exc


@app.post("/completion")
def completion(request: Request, payload: ChatRequest):
    try:
        return service.chat(payload, require_tenant_context(request))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="LLM provider unavailable") from exc


@app.post("/embeddings")
def embeddings(request: Request, payload: EmbeddingRequest):
    try:
        return service.embeddings(payload, require_tenant_context(request))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="LLM provider unavailable") from exc


@app.get("/models")
def models():
    return service.llm.models()


@app.post("/memory/store")
def memory_store(request: Request, payload: MemoryRequest):
    return service.store_memory(payload, require_tenant_context(request))


@app.post("/memory/search")
def memory_search(request: Request, payload: QueryRequest):
    return service.search_memory(payload, require_tenant_context(request))


@app.post("/memory/retrieve")
def memory_retrieve(request: Request, payload: QueryRequest):
    return service.search_memory(payload, require_tenant_context(request))


@app.post("/memory/consolidate")
def memory_consolidate(request: Request):
    return service.memory.consolidate(require_tenant_context(request))


@app.post("/guardian/validate")
def guardian_validate(request: Request, payload: MemoryRequest):
    return service.validate_memory(payload, require_tenant_context(request))


@app.get("/guardian/audit")
def guardian_audit(request: Request):
    context = require_tenant_context(request)
    return {"audit": [item for item in service.guardian.audit if item.get("tenant_id") == context.tenant_id], "reviews": [item for item in service.guardian.reviews if item.get("tenant_id") == context.tenant_id]}


@app.post("/research/query")
def research_query(request: Request, payload: QueryRequest):
    context = require_tenant_context(request)
    result = service.research.query(payload.query)
    result["tenant_id"] = context.tenant_id
    return result


@app.post("/research/report")
def research_report(request: Request, payload: QueryRequest):
    return service.research_report(payload, require_tenant_context(request))


@app.post("/chinese/articles")
def chinese_articles(request: Request, payload: ChineseArticleRequest):
    return service.chinese_hub.ingest(payload.title, payload.body, payload.script, require_tenant_context(request))


@app.post("/chinese/analyze")
def chinese_analyze(request: Request, payload: ChineseArticleRequest):
    return service.chinese_hub.ingest(payload.title, payload.body, payload.script, require_tenant_context(request))


@app.post("/analyze/code")
def analyze_code(request: Request, payload: CodeAnalysisRequest):
    return service.analyze_code(payload.code, require_tenant_context(request))


@app.post("/analyze/repository")
def analyze_repository(request: Request, files: dict[str, str]):
    return service.analysis.analyze_repository(files, require_tenant_context(request))


@app.post("/github/repositories")
def github_repository(request: Request, payload: RepositoryRequest):
    try:
        return service.github.index_repository(payload.url, payload.dependencies, require_tenant_context(request))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid repository URL") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="GitHub provider unavailable") from exc


@app.get("/github/repositories/{owner}/{repo}")
def github_analyze(request: Request, owner: str, repo: str):
    try:
        return service.github.analyze(f"{owner}/{repo}", require_tenant_context(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/sandbox/execute")
def sandbox_execute(request: Request, payload: SandboxRequest):
    try:
        return service.sandbox.execute(payload.command, payload.timeout_seconds, require_tenant_context(request))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Sandbox command denied") from exc


@app.post("/graph/entities")
def graph_entity(request: Request, payload: EntityRequest):
    return service.graph.upsert_entity(payload.entity_id, payload.labels, payload.properties, require_tenant_context(request))


@app.post("/graph/relationships")
def graph_relationship(request: Request, payload: RelationshipRequest):
    try:
        return service.graph.relate(payload.source, payload.target, payload.relationship, payload.properties, require_tenant_context(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/graph/search")
def graph_search(request: Request, payload: QueryRequest):
    return service.graph.search(payload.query, require_tenant_context(request))


@app.post("/orchestrate")
def orchestrate(request: Request, payload: WorkflowRequest):
    return service.workflow.plan(payload.task, payload.agents or None, require_tenant_context(request))


@app.post("/orchestrate/{checkpoint}/execute")
def orchestrate_execute(request: Request, checkpoint: str):
    try:
        return service.workflow.execute(checkpoint, require_tenant_context(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/orchestrate/{checkpoint}/recover")
def orchestrate_recover(request: Request, checkpoint: str):
    try:
        return service.workflow.recover(checkpoint, require_tenant_context(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/governance/proposals")
def governance_proposals(request: Request, payload: GovernanceProposalRequest):
    return service.governance.propose(payload.title, payload.body, payload.risk_score, require_tenant_context(request))


@app.post("/governance/reviews")
def governance_reviews(request: Request, payload: GovernanceReviewRequest):
    return service.governance.review(payload.decision_id, payload.approver, payload.approved, require_tenant_context(request))


@app.post("/evolution/evaluate")
def evolution_evaluate(request: Request, payload: EvaluationRequest):
    return service.evolution.evaluate(payload.metrics, require_tenant_context(request))


@app.post("/evolution/proposals")
def evolution_proposals(request: Request):
    return service.improvement_proposals(require_tenant_context(request))
