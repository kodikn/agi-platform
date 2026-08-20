import time

from fastapi.testclient import TestClient

from agi_platform.security import parse_api_keys
from api.main import app, service

client = TestClient(app)


def test_tenant_a_reads_own_resource():
    service.memory.records.clear()
    r = client.post('/memory/store', headers={'X-API-Key':'test-admin-key','X-Tenant-ID':'tenant-a'}, json={'content':'alpha secret'})
    assert r.status_code == 200
    r = client.post('/memory/search', headers={'X-API-Key':'memory-reader-key','X-Tenant-ID':'tenant-a'}, json={'query':'alpha'})
    assert r.status_code == 200
    assert len(r.json()['results']) == 1


def test_tenant_a_cannot_read_or_mutate_tenant_b():
    service.memory.records.clear()
    assert client.post('/memory/store', headers={'X-API-Key':'tenant-b-key','X-Tenant-ID':'tenant-b'}, json={'content':'bravo secret'}).status_code == 200
    r = client.post('/memory/search', headers={'X-API-Key':'memory-reader-key','X-Tenant-ID':'tenant-a'}, json={'query':'bravo'})
    assert r.status_code == 200
    assert r.json()['results'] == []
    r = client.post('/memory/store', headers={'X-API-Key':'test-admin-key','X-Tenant-ID':'tenant-b'}, json={'content':'bad write'})
    assert r.status_code == 401


def test_api_key_from_a_cannot_authenticate_as_b():
    r = client.post('/memory/search', headers={'X-API-Key':'memory-reader-key','X-Tenant-ID':'tenant-b'}, json={'query':'x'})
    assert r.status_code == 401


def test_revoked_and_expired_key_fail():
    r = client.post('/memory/search', headers={'X-API-Key':'revoked-key','X-Tenant-ID':'tenant-a'}, json={'query':'x'})
    assert r.status_code == 401
    r = client.post('/memory/search', headers={'X-API-Key':'expired-key','X-Tenant-ID':'tenant-a'}, json={'query':'x'})
    assert r.status_code == 401


def test_invalid_tenant_header_fails():
    r = client.post('/graph/search', headers={'X-API-Key':'test-admin-key','X-Tenant-ID':'tenant-b'}, json={'query':'x'})
    assert r.status_code == 401


def test_missing_tenant_context_fails_where_required():
    try:
        service.memory.search('x')
    except PermissionError as exc:
        assert 'tenant context required' in str(exc)
    else:
        raise AssertionError('expected tenant context failure')


def test_parse_api_keys_hashes_plaintext_and_honors_revocation_expiration():
    records = parse_api_keys('[{"key":"plain","tenant_id":"t","revoked":true},{"key":"old","tenant_id":"t","expires_at":1}]', None)
    assert 'plain' not in records
    assert all(not record.active(int(time.time())) for record in records.values())
