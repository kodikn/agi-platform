from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from agi_platform.config import settings
from agi_platform.readiness import platform_ready
from agi_platform.security import RateLimiter, public_paths, security_headers
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
    WorkflowResumeRequest,
)

app = FastAPI(title="AGI Platform", version="0.3.0")
service = PlatformService()
rate_limiter = RateLimiter(settings.rate_limit_per_minute)


@app.middleware("http")
async def production_controls(request: Request, call_next):
    identity = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(identity):
        return JSONResponse(status_code=429, content={"detail": "rate limit exceeded"})
    if settings.api_key and request.url.path not in public_paths():
        if request.headers.get("X-API-Key") != settings.api_key:
            return JSONResponse(status_code=401, content={"detail": "invalid API key"})
    response = await call_next(request)
    for key, value in security_headers().items():
        response.headers[key] = value
    response.headers["X-Service-Name"] = settings.service_name
    return response


class CodeAnalysisRequest(BaseModel):
    code: str = Field(min_length=1)


@app.get("/")
def root():
    return service.health()


@app.get("/health")
def health():
    return service.health()


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
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/completion")
def completion(request: ChatRequest):
    try:
        return service.chat(request)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/embeddings")
def embeddings(request: EmbeddingRequest):
    try:
        return service.embeddings(request)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/sandbox/events")
def sandbox_events():
    return {"events": service.sandbox.events()}


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
    return service.workflow.plan(request.task, request.agents or None, request.require_human_review)


@app.get("/workflows/{checkpoint}/events")
def workflow_events(checkpoint: str):
    try:
        return {"events": service.workflow.stream_events(checkpoint)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/workflows/{checkpoint}/resume")
def workflow_resume(checkpoint: str, request: WorkflowResumeRequest):
    try:
        return service.workflow.resume(checkpoint, request.human_input)
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
