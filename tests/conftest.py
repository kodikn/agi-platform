from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault(
    "AGI_API_KEYS",
    json.dumps([
        {"key": "test-admin-key", "key_id": "test-admin", "subject": "pytest-admin-a", "tenant_id": "tenant-a", "service_account_id": "svc-admin-a", "roles": ["admin"], "permissions": ["*"]},
        {"key": "memory-reader-key", "key_id": "reader", "subject": "reader-a", "tenant_id": "tenant-a", "service_account_id": "svc-reader-a", "roles": ["reader"], "permissions": ["memory:read"]},
        {"key": "tenant-b-admin-key", "key_id": "tenant-b-admin", "subject": "pytest-admin-b", "tenant_id": "tenant-b", "service_account_id": "svc-admin-b", "roles": ["admin"], "permissions": ["*"]},
        {"key": "revoked-key", "key_id": "revoked", "subject": "revoked-a", "tenant_id": "tenant-a", "service_account_id": "svc-revoked-a", "roles": ["admin"], "permissions": ["*"], "revoked": True},
        {"key": "expired-key", "key_id": "expired", "subject": "expired-a", "tenant_id": "tenant-a", "service_account_id": "svc-expired-a", "roles": ["admin"], "permissions": ["*"], "expires_at": "2000-01-01T00:00:00Z"},
        {"key": "rotated-key-new", "previous_keys": ["rotated-key-old"], "key_id": "rotated", "subject": "rotated-a", "tenant_id": "tenant-a", "service_account_id": "svc-rotated-a", "roles": ["admin"], "permissions": ["*"]},
    ]),
)
