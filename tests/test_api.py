from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["levels"] == 12


def test_architecture_level_catalog():
    response = client.get("/architecture/levels/0")
    assert response.status_code == 200
    assert response.json()["name"] == "LLM Core"
    assert "/chat" in response.json()["api"]


def test_memory_store_and_search():
    stored = client.post("/memory/store", json={"content": "LangGraph orchestrates agent workflows", "memory_type": "semantic"})
    assert stored.status_code == 200
    found = client.post("/memory/search", json={"query": "LangGraph"})
    assert found.status_code == 200
    assert found.json()["results"][0]["content"] == "LangGraph orchestrates agent workflows"


def test_code_analysis_flags_eval():
    response = client.post("/analyze/code", json={"code": "eval(user_input)"})
    assert response.status_code == 200
    assert response.json()["findings"][0]["severity"] == "high"


def test_competitive_advantages_endpoint_lists_adopted_strengths():
    response = client.get("/architecture/competitive-advantages")
    assert response.status_code == 200
    body = response.json()
    sources = {item["source"] for item in body["sources"]}
    assert {"LangGraph", "CrewAI", "AutoGen", "AutoGPT", "MetaGPT", "ChatDev", "FastAPI LangGraph template"}.issubset(sources)
    assert body["count"] >= 7


def test_orchestrator_includes_best_of_breed_capabilities():
    response = client.post("/orchestrate", json={"task": "ship production agent platform"})
    assert response.status_code == 200
    body = response.json()
    assert body["graph"]["recovery_enabled"] is True
    assert body["crew"]["flow"] == "plan -> execute -> review -> govern"
    assert body["conversation"][0]["from"] == "user"
    assert body["zero_code_contract"]["approval_required"] is True
    assert "workflow_graph" in body["competitive_capabilities"]
    assert "crew_flow" in body["competitive_capabilities"]
    assert "production_backend" in body["competitive_capabilities"]
