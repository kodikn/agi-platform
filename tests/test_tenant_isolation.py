import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)
TENANT_A = {"X-API-Key": "test-admin-key", "X-Tenant-ID": "tenant-a"}
TENANT_B = {"X-API-Key": "tenant-b-admin-key", "X-Tenant-ID": "tenant-b"}


def test_tenant_cannot_read_other_tenant_memory():
    created = client.post("/memory/store", headers=TENANT_A, json={"content": "tenant-a isolated memory marker", "memory_type": "semantic"})
    assert created.status_code == 200
    assert created.json()["tenant_id"] == "tenant-a"

    blocked = client.post("/memory/search", headers=TENANT_B, json={"query": "isolated memory marker"})
    assert blocked.status_code == 200
    assert blocked.json()["tenant_id"] == "tenant-b"
    assert blocked.json()["results"] == []


def test_tenant_cannot_update_other_tenant_memory():
    tenant_a = client.post("/memory/store", headers=TENANT_A, json={"content": "same content tenant scoped", "memory_type": "semantic"}).json()
    tenant_b = client.post("/memory/store", headers=TENANT_B, json={"content": "same content tenant scoped", "memory_type": "semantic"}).json()

    assert tenant_a["id"] != tenant_b["id"]
    assert tenant_a["tenant_id"] == "tenant-a"
    assert tenant_b["tenant_id"] == "tenant-b"


def test_tenant_cannot_read_other_tenant_workflow():
    planned = client.post("/orchestrate", headers=TENANT_A, json={"task": "tenant-a workflow"})
    assert planned.status_code == 200
    checkpoint = planned.json()["checkpoint"]

    blocked = client.post(f"/orchestrate/{checkpoint}/recover", headers=TENANT_B)
    assert blocked.status_code == 404
    assert blocked.json()["error"]["code"] == "not_found"


def test_tenant_cannot_read_other_tenant_graph():
    assert client.post("/graph/entities", headers=TENANT_A, json={"entity_id": "secret-node", "labels": ["Secret"]}).status_code == 200
    blocked = client.post("/graph/search", headers=TENANT_B, json={"query": "secret-node"})

    assert blocked.status_code == 200
    assert blocked.json()["tenant_id"] == "tenant-b"
    assert blocked.json()["nodes"] == []
    assert blocked.json()["relationships"] == []


def test_tenant_cannot_access_other_tenant_artifact():
    tenant_a = client.post("/sandbox/execute", headers=TENANT_A, json={"command": ["echo", "tenant-a-artifact"]})
    tenant_b = client.post("/sandbox/execute", headers=TENANT_B, json={"command": ["echo", "tenant-b-artifact"]})

    assert tenant_a.status_code == 200
    assert tenant_b.status_code == 200
    assert tenant_a.json()["tenant_id"] == "tenant-a"
    assert tenant_b.json()["tenant_id"] == "tenant-b"
    assert "tenant-a-artifact" not in tenant_b.json()["stdout"]
