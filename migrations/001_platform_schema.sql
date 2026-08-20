CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS providers (id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active');
CREATE TABLE IF NOT EXISTS models (id TEXT PRIMARY KEY, provider_id TEXT REFERENCES providers(id), capabilities JSONB NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS usage (id BIGSERIAL PRIMARY KEY, model_id TEXT REFERENCES models(id), tokens_used INTEGER NOT NULL, latency_ms NUMERIC NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS costs (id BIGSERIAL PRIMARY KEY, model_id TEXT REFERENCES models(id), amount NUMERIC NOT NULL, currency TEXT NOT NULL DEFAULT 'USD', created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, memory_type TEXT NOT NULL, content TEXT NOT NULL, metadata JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS memory_audit (id BIGSERIAL PRIMARY KEY, memory_id TEXT NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS memory_versions (id BIGSERIAL PRIMARY KEY, memory_id TEXT NOT NULL, version INTEGER NOT NULL, content TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS memory_reviews (id BIGSERIAL PRIMARY KEY, memory_id TEXT NOT NULL, status TEXT NOT NULL, risk_score NUMERIC NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS repositories (id BIGSERIAL PRIMARY KEY, url TEXT NOT NULL UNIQUE, metadata JSONB NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS commits (id TEXT PRIMARY KEY, repository_id BIGINT REFERENCES repositories(id), message TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS issues (id BIGSERIAL PRIMARY KEY, repository_id BIGINT REFERENCES repositories(id), title TEXT NOT NULL, state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pull_requests (id BIGSERIAL PRIMARY KEY, repository_id BIGINT REFERENCES repositories(id), title TEXT NOT NULL, state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dependencies (id BIGSERIAL PRIMARY KEY, repository_id BIGINT REFERENCES repositories(id), name TEXT NOT NULL, version TEXT);
CREATE TABLE IF NOT EXISTS architecture_decisions (id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS architecture_reviews (id BIGSERIAL PRIMARY KEY, decision_id BIGINT REFERENCES architecture_decisions(id), risk_score NUMERIC NOT NULL, status TEXT NOT NULL);

-- Canonical production control-plane schema. Existing prototype tables above are kept
-- for compatibility; these tables establish durable ownership for the domain kernel.
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    lifecycle_state TEXT NOT NULL DEFAULT 'CREATED' CHECK (lifecycle_state IN ('CREATED', 'ACTIVE', 'ARCHIVED', 'DELETED')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    email TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL DEFAULT 'CREATED' CHECK (lifecycle_state IN ('CREATED', 'ACTIVE', 'ARCHIVED', 'DELETED')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email)
);

CREATE TABLE IF NOT EXISTS agent_roles (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    permissions JSONB NOT NULL DEFAULT '[]',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    role_id TEXT NOT NULL REFERENCES agent_roles(id) ON DELETE RESTRICT,
    capabilities JSONB NOT NULL DEFAULT '[]',
    allowed_tools JSONB NOT NULL DEFAULT '[]',
    allowed_resources JSONB NOT NULL DEFAULT '[]',
    risk_level TEXT NOT NULL DEFAULT 'LOW' CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    budget JSONB NOT NULL DEFAULT '{}',
    timeout_seconds INTEGER NOT NULL DEFAULT 60 CHECK (timeout_seconds > 0),
    max_iterations INTEGER NOT NULL DEFAULT 10 CHECK (max_iterations >= 0),
    max_tool_calls INTEGER NOT NULL DEFAULT 20 CHECK (max_tool_calls >= 0),
    lifecycle_state TEXT NOT NULL DEFAULT 'CREATED' CHECK (lifecycle_state IN ('CREATED', 'ACTIVE', 'ARCHIVED', 'DELETED')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tools (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    input_schema JSONB NOT NULL DEFAULT '{}',
    output_schema JSONB NOT NULL DEFAULT '{}',
    required_capabilities JSONB NOT NULL DEFAULT '[]',
    timeout_seconds INTEGER NOT NULL DEFAULT 30 CHECK (timeout_seconds > 0),
    network_access TEXT NOT NULL DEFAULT 'none',
    filesystem_access TEXT NOT NULL DEFAULT 'none',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS tool_permissions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    tool_id TEXT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    capability TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT 'execute',
    risk_level TEXT NOT NULL DEFAULT 'LOW' CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, tool_id, capability, action)
);

CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    owner_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    state TEXT NOT NULL DEFAULT 'CREATED' CHECK (state IN ('CREATED', 'PLANNED', 'RUNNING', 'WAITING', 'PAUSED', 'FAILED', 'RECOVERING', 'COMPLETED', 'CANCELLED')),
    idempotency_key TEXT,
    lifecycle_state TEXT NOT NULL DEFAULT 'CREATED' CHECK (lifecycle_state IN ('CREATED', 'ACTIVE', 'ARCHIVED', 'DELETED')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    current_state TEXT NOT NULL DEFAULT 'CREATED' CHECK (current_state IN ('CREATED', 'PLANNED', 'RUNNING', 'WAITING', 'PAUSED', 'FAILED', 'RECOVERING', 'COMPLETED', 'CANCELLED')),
    checkpoint_id TEXT,
    event_sequence BIGINT NOT NULL DEFAULT 0 CHECK (event_sequence >= 0),
    idempotency_key TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, workflow_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    state TEXT NOT NULL DEFAULT 'PENDING' CHECK (state IN ('PENDING', 'READY', 'RUNNING', 'WAITING_TOOL', 'WAITING_APPROVAL', 'RETRYING', 'FAILED', 'COMPLETED', 'CANCELLED')),
    idempotency_key TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, workflow_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS task_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    current_state TEXT NOT NULL DEFAULT 'PENDING' CHECK (current_state IN ('PENDING', 'READY', 'RUNNING', 'WAITING_TOOL', 'WAITING_APPROVAL', 'RETRYING', 'FAILED', 'COMPLETED', 'CANCELLED')),
    attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    workflow_run_id TEXT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    event_sequence BIGINT NOT NULL CHECK (event_sequence >= 0),
    state JSONB NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, workflow_run_id, event_sequence)
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    event_version INTEGER NOT NULL DEFAULT 1 CHECK (event_version > 0),
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    correlation_id TEXT,
    request_id TEXT,
    workflow_id TEXT REFERENCES workflows(id) ON DELETE SET NULL,
    task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
    agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
    actor_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    sequence BIGINT,
    payload JSONB NOT NULL DEFAULT '{}',
    UNIQUE (tenant_id, workflow_id, sequence)
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY REFERENCES events(event_id) ON DELETE RESTRICT,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    result TEXT NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'LOW' CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    policy_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agents_tenant_role ON agents(tenant_id, role_id);
CREATE INDEX IF NOT EXISTS idx_tools_tenant_name ON tools(tenant_id, name);
CREATE INDEX IF NOT EXISTS idx_workflows_tenant_state ON workflows(tenant_id, state);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_tenant_state ON workflow_runs(tenant_id, current_state);
CREATE INDEX IF NOT EXISTS idx_tasks_workflow_state ON tasks(tenant_id, workflow_id, state);
CREATE INDEX IF NOT EXISTS idx_events_tenant_workflow_sequence ON events(tenant_id, workflow_id, sequence);
CREATE INDEX IF NOT EXISTS idx_events_correlation ON events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_created ON audit_events(tenant_id, created_at);
