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
