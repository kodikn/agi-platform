import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_high_risk_endpoint_requires_api_key():
    response = client.post("/sandbox/execute", json={"command": ["python", "-c", "print('x')"]})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthenticated"
    assert body["error"]["request_id"]


def test_endpoint_requires_explicit_permission():
    response = client.post("/sandbox/execute", headers={"X-API-Key": "memory-reader-key", "X-Tenant-ID": "tenant-a"}, json={"command": ["python", "-c", "print('x')"]})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_tenant_header_must_match_api_key_tenant():
    response = client.post("/memory/search", headers={"X-API-Key": "memory-reader-key", "X-Tenant-ID": "tenant-b"}, json={"query": "anything"})
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Valid API key required."
