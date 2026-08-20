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
api_keys = parse_api_keys(getattr(settings, "api_keys", None), settings.api_key)


@app.middleware("http")
async def production_controls(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or request_id()
    request.state.request_id = rid
    identity_key = request.headers.get("X-API-Key") or (request.client.host if request.client else "unknown")
    if not rate_limiter.allow(identity_key):
        response = canonical_error("rate_limited", "Rate limit exceeded.", rid, 429)
        response.headers["X-Request-ID"] = rid
        return apply_production_headers(response, settings.service_name)

    if request.url.path not in public_paths():
        permission = route_permission(request.method, request.url.path)
        if api_keys:
            identity = authenticate_request(request, api_keys)
            if identity is None:
                response = canonical_error("unauthenticated", "Valid API key required.", rid, 401)
                response.headers["X-Request-ID"] = rid
                return apply_production_headers(response, settings.service_name)
            request.state.identity = identity
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
    message = exc.detail if isinstance(exc.detail, str) and exc.status_code < 500 else "Request could not be completed."
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
    return {"api_key_required": bool(settings.api_key), "rate_limit_per_minute": settings.rate_limit_per_minute, "public_paths": sorted(public_paths())}


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
def chat(request: ChatRequest):
    try:
        return service.chat(request)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="LLM provider unavailable") from exc


@app.post("/completion")
def completion(request: ChatRequest):
    try:
        return service.chat(request)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="LLM provider unavailable") from exc


@app.post("/embeddings")
def embeddings(request: EmbeddingRequest):
    try:
        return service.embeddings(request)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="LLM provider unavailable") from exc


@app.get("/models")
def models():
    return service.llm.models()


@app.post("/memory/store")
def memory_store(request: MemoryRequest):
    return service.store_memory(request)


@app.post("/memory/search")
def memory_search(request: QueryRequest):
    return service.search_memory(request)


@app.post("/memory/retrieve")
def memory_retrieve(request: QueryRequest):
    return service.search_memory(request)


@app.post("/memory/consolidate")
def memory_consolidate():
    return service.memory.consolidate()


@app.post("/guardian/validate")
def guardian_validate(request: MemoryRequest):
    return service.validate_memory(request)


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
        raise HTTPException(status_code=422, detail="Invalid repository URL") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="GitHub provider unavailable") from exc


@app.get("/github/repositories/{owner}/{repo}")
def github_analyze(owner: str, repo: str):
    try:
        return service.github.analyze(f"{owner}/{repo}")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/sandbox/execute")
def sandbox_execute(request: SandboxRequest):
    try:
        return service.sandbox.execute(request.command, request.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Sandbox command denied") from exc


@app.post("/graph/entities")
def graph_entity(request: EntityRequest):
    return service.graph.upsert_entity(request.entity_id, request.labels, request.properties)


@app.post("/graph/relationships")
def graph_relationship(request: RelationshipRequest):
    try:
        return service.graph.relate(request.source, request.target, request.relationship, request.properties)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/graph/search")
def graph_search(request: QueryRequest):
    return service.graph.search(request.query)


@app.post("/orchestrate")
def orchestrate(request: WorkflowRequest):
    return service.workflow.plan(request.task, request.agents or None)


@app.post("/orchestrate/{checkpoint}/execute")
def orchestrate_execute(checkpoint: str):
    try:
        return service.workflow.execute(checkpoint)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/orchestrate/{checkpoint}/recover")
def orchestrate_recover(checkpoint: str):
    try:
        return service.workflow.recover(checkpoint)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/governance/proposals")
def governance_proposals(request: GovernanceProposalRequest):
    return service.governance.propose(request.title, request.body, request.risk_score)


@app.post("/governance/reviews")
def governance_reviews(request: GovernanceReviewRequest):
    return service.governance.review(request.decision_id, request.approver, request.approved)


@app.post("/evolution/evaluate")
def evolution_evaluate(request: EvaluationRequest):
    return service.evolution.evaluate(request.metrics)


@app.post("/evolution/proposals")
def evolution_proposals():
    return service.improvement_proposals()
