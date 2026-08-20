from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_level_0_llm_core_reports_real_provider_configuration():
    models = client.get("/models")
    assert models.status_code == 200
    assert "openai" in models.json()["providers"]
    chat = client.post("/chat", json={"message": "route this request", "model": "gpt-4.1"})
    assert chat.status_code in {200, 503}
    if chat.status_code == 503:
        assert "provider" in chat.json()["detail"]


def test_level_1_and_2_memory_guardian():
    stored = client.post("/memory/store", json={"content": "semantic memory supports retrieval ranking", "memory_type": "semantic"})
    assert stored.status_code == 200
    search = client.post("/memory/search", json={"query": "retrieval ranking"})
    assert search.json()["results"][0]["score"] > 0
    review = client.post("/guardian/validate", json={"content": "semantic memory supports retrieval ranking", "memory_type": "semantic"})
    assert review.status_code == 200
    assert review.json()["decision"] in {"approve", "review"}


def test_level_3_and_4_research_hubs():
    report = client.post("/research/report", json={"query": "CVE research 8.8.8.8"})
    assert report.status_code == 200
    assert "iocs" in report.json()
    chinese = client.post("/chinese/articles", json={"title": "威胁研究", "body": "发现漏洞和攻击 1.1.1.1"})
    assert chinese.status_code == 200
    assert chinese.json()["classification"] == "threat-intelligence"
    assert "1.1.1.1" in chinese.json()["iocs"]


def test_level_5_and_6_analysis_and_github(monkeypatch):
    from api.main import service

    analysis = client.post("/analyze/code", json={"code": "password = 'secret'\neval(password)"})
    assert analysis.status_code == 200
    assert analysis.json()["metrics"]["findings_count"] == 2

    def index_repository(url, dependencies=None):
        record = {"full_name": "openai/codex", "url": url, "default_branch": "main", "stars": 1, "open_issues": 0, "dependencies": dependencies or [], "contributors": ["octocat"]}
        service.github.repositories["openai/codex"] = record
        return record

    monkeypatch.setattr(service.github, "index_repository", index_repository)
    repo = client.post("/github/repositories", json={"url": "https://github.com/openai/codex", "dependencies": ["fastapi"]})
    assert repo.status_code == 200
    analyzed = client.get("/github/repositories/openai/codex")
    assert analyzed.json()["dependency_count"] == 1


def test_level_7_sandbox_policy_and_execution():
    executed = client.post("/sandbox/execute", json={"command": ["echo", "safe"]})
    assert executed.status_code == 200
    body = executed.json()
    assert body["stdout"] == "safe\n"
    assert body["policy"]["memory_bytes"] > 0
    assert body["policy"]["network"] == "host-disabled-by-policy"
    assert body["policy"]["network_isolation"] is False
    assert body["policy"]["isolation_boundary"] == "subprocess_resource_limits_only"
    blocked = client.post("/sandbox/execute", json={"command": ["curl", "https://example.com"]})
    assert blocked.status_code == 403


def test_level_8_knowledge_graph():
    assert client.post("/graph/entities", json={"entity_id": "agent:architect", "labels": ["Agent"]}).status_code == 200
    assert client.post("/graph/entities", json={"entity_id": "level:0", "labels": ["Level"]}).status_code == 200
    edge = client.post("/graph/relationships", json={"source": "agent:architect", "target": "level:0", "relationship": "DESIGNS"})
    assert edge.status_code == 200
    found = client.post("/graph/search", json={"query": "agent"})
    assert found.json()["relationships"]


def test_level_9_to_11_orchestration_governance_evolution():
    workflow = client.post("/orchestrate", json={"task": "implement levels"})
    assert workflow.status_code == 200
    assert workflow.json()["status"] == "planned"
    proposal = client.post("/governance/proposals", json={"title": "Adopt LangGraph", "body": "Use checkpoints", "risk_score": 0.2})
    assert proposal.status_code == 200
    assert proposal.json()["status"] == "approved"
    evaluation = client.post("/evolution/evaluate", json={"metrics": {"success_rate": 0.9, "failure_rate": 0.1, "tool_effectiveness": 0.7}})
    assert evaluation.status_code == 200
    assert len(evaluation.json()["proposals"]) == 2


def test_architecture_catalog_matches_target_module_tree():
    expected_modules = {
        0: ("providers/", "router/", "registry/", "telemetry/"),
        1: ("working_memory/", "episodic_memory/", "semantic_memory/", "retrieval/", "consolidation/"),
        2: ("validator/", "deduplication/", "approval/", "audit/", "rollback/"),
        3: ("collectors/", "extraction/", "ranking/", "reporting/"),
        4: ("ingestion/", "translation/", "classification/", "threat_extraction/", "enrichment/"),
        5: ("static_analysis/", "dependency_analysis/", "architecture_analysis/", "security_analysis/", "repository_analysis/"),
        6: ("repository_indexer/", "commit_analyzer/", "issue_analyzer/", "pr_analyzer/", "dependency_graph/", "knowledge_extractor/"),
        7: ("runtime/", "isolation/", "monitoring/", "artifacts/", "cleanup/"),
        8: ("entities/", "relationships/", "graph_store/", "graph_search/", "analytics/"),
        9: ("workflow_engine/", "task_router/", "agent_router/", "checkpoint_manager/", "recovery_manager/", "planner/"),
        10: ("proposals/", "decisions/", "reviews/", "risk_management/", "approvals/"),
        11: ("telemetry/", "evaluation/", "optimization/", "learning/", "pattern_discovery/", "improvement_engine/"),
    }

    for level, modules in expected_modules.items():
        response = client.get(f"/architecture/levels/{level}")
        assert response.status_code == 200
        assert tuple(response.json()["modules"]) == modules


def test_sandbox_capability_check_is_available_but_not_production_isolated():
    from api.main import service

    capability = service.sandbox.capability_check()
    assert capability["status"] == "ready"
    assert capability["production_ready"] is False
    assert capability["result"]["policy"]["network"] == "host-disabled-by-policy"
    assert capability["result"]["policy"]["network_isolation"] is False
