from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_platform_readiness_covers_all_levels():
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert len(body["levels"]) == 12
    assert all(level["status"] == "ready" for level in body["levels"])
    assert all(len(level["criteria"]) == 5 for level in body["levels"])


def test_metrics_and_security_headers_are_exposed():
    client.post("/memory/store", json={"content": "collect production metrics", "memory_type": "semantic"})
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "memories_stored" in metrics.text
    assert metrics.headers["X-Content-Type-Options"] == "nosniff"
    policy = client.get("/security/policy")
    assert policy.status_code == 200
    assert policy.json()["rate_limit_per_minute"] > 0
