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
        {"key": "test-admin-key", "key_id": "test-admin", "subject": "pytest", "tenant_id": "tenant-a", "roles": ["admin"], "permissions": ["*"]},
        {"key": "memory-reader-key", "key_id": "reader", "subject": "reader", "tenant_id": "tenant-a", "roles": ["reader"], "permissions": ["memory:read"]},
        {"key": "tenant-b-key", "key_id": "tenant-b", "subject": "tenant-b", "tenant_id": "tenant-b", "roles": ["admin"], "permissions": ["*"]},
        {"key": "revoked-key", "key_id": "revoked", "subject": "revoked", "tenant_id": "tenant-a", "roles": ["reader"], "permissions": ["memory.read"], "revoked": True},
        {"key": "expired-key", "key_id": "expired", "subject": "expired", "tenant_id": "tenant-a", "roles": ["reader"], "permissions": ["memory.read"], "expires_at": 1},
    ]),
)

os.environ.setdefault("AGI_REDIS_REQUIRED", "false")
