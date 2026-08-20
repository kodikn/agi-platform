from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from pydantic import BaseModel, Field

from .analysis.core import AnalysisLayer
from .catalog import PLATFORM_LEVELS, get_level
from .competitive import competitive_strengths
from .chinese_hub.core import ChineseResearchHub
from .evolution.core import SelfImprovementEngine
from .github_intel.core import GitHubIntelligence
from .governance.core import ArchitectureGovernance
from .guardian.core import MemoryGuardian
from .knowledge_graph.core import KnowledgeGraph
from .llm.core import LLMCore
from .memory.core import MemoryLayer
from .orchestration import WorkflowEngine
from .research.core import ResearchLayer
from .sandbox.core import SandboxLab
from .security import TenantContext
from .telemetry import TelemetryRegistry
from .tool_registry import ToolRegistry


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    model: str | None = None
    stream: bool = False


class EmbeddingRequest(BaseModel):
    text: str = Field(min_length=1)


class MemoryRequest(BaseModel):
    content: str = Field(min_length=1)
    memory_type: str = "semantic"
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


class ChineseArticleRequest(BaseModel):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    script: str = "simplified"


class RepositoryRequest(BaseModel):
    url: str = Field(min_length=1)
    dependencies: list[str] = Field(default_factory=list)


class SandboxRequest(BaseModel):
    command: list[str] = Field(min_length=1)
    timeout_seconds: int = Field(default=5, ge=1, le=30)


class EntityRequest(BaseModel):
    entity_id: str = Field(min_length=1)
    labels: list[str] = Field(min_length=1)
    properties: dict[str, Any] = Field(default_factory=dict)


class RelationshipRequest(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    relationship: str = Field(min_length=1)
    properties: dict[str, Any] = Field(default_factory=dict)


class WorkflowRequest(BaseModel):
    task: str = Field(min_length=1)
    agents: list[str] = Field(default_factory=list)


class GovernanceProposalRequest(BaseModel):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)


class GovernanceReviewRequest(BaseModel):
    decision_id: int = Field(ge=1)
    approver: str = Field(min_length=1)
    approved: bool


class EvaluationRequest(BaseModel):
    metrics: dict[str, float]


class PlatformService:
    def __init__(self) -> None:
        self.llm = LLMCore()
        self.memory = MemoryLayer()
        self.guardian = MemoryGuardian()
        self.research = ResearchLayer()
        self.chinese_hub = ChineseResearchHub()
        self.analysis = AnalysisLayer()
        self.github = GitHubIntelligence()
        self.sandbox = SandboxLab()
        self.graph = KnowledgeGraph()
        self.workflow = WorkflowEngine()
        self.governance = ArchitectureGovernance()
        self.evolution = SelfImprovementEngine()
        self.telemetry = TelemetryRegistry()
        self.tool_registry = ToolRegistry()

    def health(self) -> dict[str, Any]:
        return {"status": "ok", "levels": len(PLATFORM_LEVELS), "timestamp": int(time.time())}

    def levels(self) -> list[dict[str, Any]]:
        return [asdict(level) for level in PLATFORM_LEVELS]

    def level(self, level: int) -> dict[str, Any]:
        return asdict(get_level(level))

    def competitive_advantages(self) -> dict[str, Any]:
        return {"sources": competitive_strengths(), "count": len(competitive_strengths())}

    def tools(self) -> dict[str, Any]:
        return self.tool_registry.list_tools()

    def mcp_manifest(self) -> dict[str, Any]:
        return self.tool_registry.mcp_manifest()

    def chat(self, request: ChatRequest, context: TenantContext) -> dict[str, Any]:
        with self.telemetry.timer("level_operation", level="0", operation="chat"):
            result = self.llm.complete(request.message, request.model, request.stream)
            self.telemetry.increment("tokens_used", result["usage"]["input_tokens"] + result["usage"]["output_tokens"], level="0")
            self.telemetry.increment("cost", result["metrics"]["cost"], level="0")
            return result

    def embeddings(self, request: EmbeddingRequest, context: TenantContext) -> dict[str, Any]:
        with self.telemetry.timer("level_operation", level="0", operation="embeddings"):
            return self.llm.embeddings(request.text)

    def store_memory(self, request: MemoryRequest, context: TenantContext) -> dict[str, Any]:
        with self.telemetry.timer("level_operation", level="1", operation="store_memory"):
            record = self.memory.store(request.content, request.memory_type, request.metadata, context)
            self.guardian.version(record)
            self.telemetry.increment("memories_stored", level="1")
            return record

    def search_memory(self, request: QueryRequest, context: TenantContext) -> dict[str, Any]:
        with self.telemetry.timer("level_operation", level="1", operation="search_memory"):
            return self.memory.search(request.query, request.limit, context)

    def validate_memory(self, request: MemoryRequest, context: TenantContext) -> dict[str, Any]:
        with self.telemetry.timer("level_operation", level="2", operation="validate_memory"):
            candidate = self.memory.store(request.content, request.memory_type, request.metadata, context)
            tenant_records = [record for record in self.memory.records.values() if record.get("tenant_id") == context.tenant_id]
            result = self.guardian.validate(candidate, tenant_records)
            self.telemetry.increment("memory_reviews", level="2")
            return result

    def research_report(self, request: QueryRequest, context: TenantContext) -> dict[str, Any]:
        with self.telemetry.timer("level_operation", level="3", operation="research_report"):
            return self.research.report(request.query, context=context)

    def analyze_code(self, code: str, context: TenantContext) -> dict[str, Any]:
        with self.telemetry.timer("level_operation", level="5", operation="analyze_code"):
            return self.analysis.analyze_code(code, context=context)

    def improvement_proposals(self, context: TenantContext) -> dict[str, Any]:
        with self.telemetry.timer("level_operation", level="11", operation="improvement_proposals"):
            return self.evolution.evaluate({"success_rate": 0.94, "failure_rate": 0.06, "tool_effectiveness": 0.79, "agent_effectiveness": 0.9}, context=context)
