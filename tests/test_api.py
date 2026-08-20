import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)
AUTH = {"X-API-Key": "test-admin-key", "X-Tenant-ID": "tenant-a"}


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
    stored = client.post("/memory/store", headers=AUTH, json={"content": "LangGraph orchestrates agent workflows", "memory_type": "semantic"})
    assert stored.status_code == 200
    found = client.post("/memory/search", headers=AUTH, json={"query": "LangGraph"})
    assert found.status_code == 200
    assert found.json()["results"][0]["content"] == "LangGraph orchestrates agent workflows"


def test_code_analysis_flags_eval():
    response = client.post("/analyze/code", headers=AUTH, json={"code": "eval(user_input)"})
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
    response = client.post("/orchestrate", headers=AUTH, json={"task": "ship production agent platform"})
    assert response.status_code == 200
    body = response.json()
    assert body["graph"]["recovery_enabled"] is True
    assert body["crew"]["flow"] == "plan -> execute -> review -> govern"
    assert body["conversation"][0]["from"] == "user"
    assert body["zero_code_contract"]["approval_required"] is True
    assert "workflow_graph" in body["competitive_capabilities"]
    assert "crew_flow" in body["competitive_capabilities"]
    assert "production_backend" in body["competitive_capabilities"]


def test_tool_registry_exposes_governed_contracts():
    response = client.get("/tools")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 5
    sandbox = next(tool for tool in body["tools"] if tool["name"] == "sandbox.execute")
    assert sandbox["side_effects"] is True
    assert sandbox["risk"] == "high"
    assert "sandbox:execute" in sandbox["permissions"]


def test_mcp_manifest_lists_approved_tools():
    response = client.get("/mcp/manifest")
    assert response.status_code == 200
    body = response.json()
    assert body["protocol"] == "mcp-compatible"
    assert body["capabilities"]["tools"] is True
    names = {tool["name"] for tool in body["tools"]}
    assert {"memory.search", "research.report", "sandbox.execute"}.issubset(names)


def test_orchestrator_executes_and_recovers_persistent_workflow():
    planned = client.post("/orchestrate", headers=AUTH, json={"task": "deliver executable workflow", "agents": ["architect", "implementer"]})
    assert planned.status_code == 200
    checkpoint = planned.json()["checkpoint"]

    executed = client.post(f"/orchestrate/{checkpoint}/execute", headers=AUTH)
    assert executed.status_code == 200
    body = executed.json()
    assert body["status"] == "completed"
    assert all(step["status"] == "completed" for step in body["steps"])
    assert body["events"][-1]["type"] == "workflow.completed"
    assert body["graph"]["state_store"]

    recovered = client.post(f"/orchestrate/{checkpoint}/recover", headers=AUTH)
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "recovered"
    assert recovered.json()["checkpoint"] == checkpoint
