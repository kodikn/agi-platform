from fastapi.testclient import TestClient

from api.main import app, service
from agi_platform.security import TenantContext

client = TestClient(app)
AUTH_A = {"X-API-Key": "test-admin-key", "X-Tenant-ID": "tenant-a"}
AUTH_B = {"X-API-Key": "tenant-b-admin-key", "X-Tenant-ID": "tenant-b"}


def test_tenant_a_reads_own_resource():
    stored = client.post("/memory/store", headers=AUTH_A, json={"content": "tenant-a private memory", "memory_type": "semantic"})
    assert stored.status_code == 200
    assert stored.json()["tenant_id"] == "tenant-a"

    found = client.post("/memory/search", headers=AUTH_A, json={"query": "private memory"})
    assert found.status_code == 200
    assert found.json()["tenant_id"] == "tenant-a"
    assert any(item["content"] == "tenant-a private memory" for item in found.json()["results"])


def test_tenant_a_cannot_read_tenant_b_resource():
    assert client.post("/memory/store", headers=AUTH_B, json={"content": "tenant-b isolated memory", "memory_type": "semantic"}).status_code == 200

    found = client.post("/memory/search", headers=AUTH_A, json={"query": "isolated memory"})
    assert found.status_code == 200
    assert all(item["tenant_id"] == "tenant-a" for item in found.json()["results"])
    assert all(item["content"] != "tenant-b isolated memory" for item in found.json()["results"])


def test_tenant_a_cannot_mutate_tenant_b_graph_resource():
    assert client.post("/graph/entities", headers=AUTH_B, json={"entity_id": "tenant-b-node", "labels": ["Secret"]}).status_code == 200
    relationship = client.post("/graph/relationships", headers=AUTH_A, json={"source": "tenant-b-node", "target": "tenant-b-node", "relationship": "OWNS"})
    assert relationship.status_code == 404


def test_api_key_from_a_cannot_authenticate_as_b():
    response = client.post("/memory/search", headers={"X-API-Key": "test-admin-key", "X-Tenant-ID": "tenant-b"}, json={"query": "anything"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_revoked_key_fails():
    response = client.post("/memory/search", headers={"X-API-Key": "revoked-key", "X-Tenant-ID": "tenant-a"}, json={"query": "anything"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_expired_key_fails():
    response = client.post("/memory/search", headers={"X-API-Key": "expired-key", "X-Tenant-ID": "tenant-a"}, json={"query": "anything"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_invalid_tenant_header_fails():
    response = client.post("/memory/search", headers={"X-API-Key": "tenant-b-admin-key", "X-Tenant-ID": "tenant-a"}, json={"query": "anything"})
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Valid API key required."


def test_missing_tenant_context_fails_where_required():
    try:
        service.memory.search("anything")
    except ValueError as exc:
        assert "tenant context" in str(exc)
    else:
        raise AssertionError("missing tenant context should fail closed")


def test_rotated_previous_key_still_authenticates_until_retired():
    response = client.post("/memory/store", headers={"X-API-Key": "rotated-key-old", "X-Tenant-ID": "tenant-a"}, json={"content": "rotated key memory", "memory_type": "semantic"})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-a"


def test_api_keys_are_hashed_at_rest():
    from api.main import identity_registry

    hashes = {record.key_hash for record in identity_registry.api_keys.values()}
    assert "test-admin-key" not in hashes
    assert all(len(value) == 64 for value in hashes)

    context = TenantContext("tenant-a", "direct-test", "direct", frozenset(), frozenset({"memory:read"}))
    service.memory.search("anything", context=context)
