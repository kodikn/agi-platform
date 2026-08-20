CREATE TABLE IF NOT EXISTS service_accounts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    subject TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, subject)
);

CREATE TABLE IF NOT EXISTS permissions (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roles (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    active BOOLEAN NOT NULL DEFAULT true,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id TEXT NOT NULL REFERENCES permissions(id) ON DELETE RESTRICT,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS service_account_roles (
    service_account_id TEXT NOT NULL REFERENCES service_accounts(id) ON DELETE CASCADE,
    role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (service_account_id, role_id)
);

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    service_account_id TEXT REFERENCES service_accounts(id) ON DELETE CASCADE,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL DEFAULT '',
    scopes JSONB NOT NULL DEFAULT '[]',
    revoked BOOLEAN NOT NULL DEFAULT false,
    expires_at TIMESTAMPTZ,
    rotated_from_key_id TEXT REFERENCES api_keys(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    CHECK (service_account_id IS NOT NULL OR user_id IS NOT NULL),
    UNIQUE (tenant_id, key_hash)
);

CREATE TABLE IF NOT EXISTS api_key_audit_events (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    api_key_id TEXT REFERENCES api_keys(id) ON DELETE SET NULL,
    actor_id TEXT,
    action TEXT NOT NULL CHECK (action IN ('created', 'authenticated', 'revoked', 'rotated', 'expired', 'denied')),
    result TEXT NOT NULL CHECK (result IN ('allowed', 'denied', 'success')),
    reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_service_accounts_tenant_subject ON service_accounts(tenant_id, subject);
CREATE INDEX IF NOT EXISTS idx_roles_tenant_name ON roles(tenant_id, name);
CREATE INDEX IF NOT EXISTS idx_role_permissions_tenant ON role_permissions(tenant_id, role_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_tenant ON user_roles(tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_service_account_roles_tenant ON service_account_roles(tenant_id, service_account_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_tenant_active ON api_keys(tenant_id, revoked, expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_key_audit_tenant_created ON api_key_audit_events(tenant_id, created_at);
