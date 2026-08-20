from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)
AUTH = {"X-API-Key": "test-admin-key", "X-Tenant-ID": "tenant-a"}


def test_platform_readiness_reports_honest_production_controls():
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"not-ready", "degraded"}
    assert len(body["levels"]) == 12
    assert any(level["status"] == "RED" for level in body["levels"])
    assert all(len(level["criteria"]) == 5 for level in body["levels"])
    assert all(level["controls"] for level in body["levels"])


def test_metrics_and_security_headers_are_exposed():
    client.post("/memory/store", headers=AUTH, json={"content": "collect production metrics", "memory_type": "semantic"})
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "memories_stored" in metrics.text
    assert metrics.headers["X-Content-Type-Options"] == "nosniff"
    policy = client.get("/security/policy")
    assert policy.status_code == 200
    assert policy.json()["rate_limit_per_minute"] > 0


def test_liveness_endpoint_is_public_and_lightweight():
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_kubernetes_manifest_has_production_runtime_controls():
    manifest = Path("k8s/api.yaml").read_text()

    assert "image: agi-platform:0.3.0" in manifest
    assert "image: agi-platform:latest" not in manifest
    assert "livenessProbe:" in manifest
    assert "startupProbe:" in manifest
    assert "resources:" in manifest
    assert "runAsNonRoot: true" in manifest
    assert "allowPrivilegeEscalation: false" in manifest
    assert "secretRef:" in manifest
    assert "configMapRef:" in manifest


def test_compose_stack_has_local_healthchecks():
    compose = Path("docker-compose.yml").read_text()

    assert "condition: service_healthy" in compose
    assert "http://localhost:8000/live" in compose
    assert "pg_isready -U $${POSTGRES_USER:-agi} -d $${POSTGRES_DB:-agi}" in compose
    assert "${POSTGRES_PASSWORD:-agi}" in compose
    assert "neo4j/${NEO4J_PASSWORD:-agi-platform}" in compose
    assert "redis-cli" in compose
