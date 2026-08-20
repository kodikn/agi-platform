from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_authentication_failure_uses_canonical_error():
    r = client.post("/memory/store", json={"content": "x"})
    body = r.json()
    assert r.status_code == 401
    assert set(body) == {"error"}
    assert {"code", "message", "request_id"} <= set(body["error"])


def test_authorization_failure_does_not_leak_internal_reason():
    r = client.post("/memory/store", headers={"X-API-Key": "memory-reader-key", "X-Tenant-ID": "tenant-a"}, json={"content": "x"})
    assert r.status_code == 403
    assert r.json()["error"]["message"] == "Permission denied."


def test_unexpected_exception_response_is_sanitized(monkeypatch):
    def boom():
        raise RuntimeError("postgresql://user:secret@db/app /workspace/agi-platform/file.py SELECT * FROM users")
    monkeypatch.setattr("api.main.platform_ready", boom)
    r = client.get("/ready")
    text = r.text.lower()
    assert r.status_code == 500
    assert "postgresql://" not in text
    assert "/workspace" not in text
    assert "select *" not in text
    assert "secret" not in text
