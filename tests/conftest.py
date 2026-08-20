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
    ]),
)
