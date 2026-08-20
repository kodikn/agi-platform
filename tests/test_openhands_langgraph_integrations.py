from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_openhands_style_sandbox_action_observation_events():
    executed = client.post("/sandbox/execute", json={"command": ["echo", "evented"]})
    assert executed.status_code == 200
    events = client.get("/sandbox/events")
    assert events.status_code == 200
    kinds = [event["kind"] for event in events.json()["events"]]
    assert "sandbox.action" in kinds
    assert "sandbox.observation" in kinds
    assert any(event["visible_to_llm"] for event in events.json()["events"])


def test_langgraph_style_checkpoint_interrupt_resume_and_event_stream():
    planned = client.post("/orchestrate", json={"task": "review risky migration", "require_human_review": True})
    assert planned.status_code == 200
    body = planned.json()
    assert body["status"] == "paused"
    checkpoint = body["checkpoint"]

    events = client.get(f"/workflows/{checkpoint}/events")
    assert events.status_code == 200
    assert any(event["kind"] == "workflow.interrupt" for event in events.json()["events"])

    resumed = client.post(f"/workflows/{checkpoint}/resume", json={"human_input": {"approved": True, "reviewer": "architect"}})
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "running"
    assert resumed.json()["state"]["human_input"]["approved"] is True
