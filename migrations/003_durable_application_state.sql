-- Durable application state model. Idempotent, additive, and non-destructive.
-- Existing data migration: backfill tenant_id for legacy rows before making tenant_id NOT NULL in a future migration.

CREATE TABLE IF NOT EXISTS agent_versions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    config JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','RETIRED','DELETED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, agent_id, version)
);

CREATE TABLE IF NOT EXISTS workflow_tasks (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    workflow_run_id TEXT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','RUNNING','WAITING','SUCCEEDED','FAILED','CANCELLED','TIMED_OUT','RECOVERING')),
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    idempotency_key TEXT NOT NULL,
    retry_policy JSONB NOT NULL DEFAULT '{"max_attempts":3,"backoff":"exponential"}',
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS workflow_attempts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    workflow_task_id TEXT NOT NULL REFERENCES workflow_tasks(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    status TEXT NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING','SUCCEEDED','FAILED','TIMED_OUT')),
    worker_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    error TEXT,
    UNIQUE (tenant_id, workflow_task_id, attempt_number)
);

CREATE TABLE IF NOT EXISTS workflow_artifacts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    workflow_run_id TEXT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    workflow_task_id TEXT REFERENCES workflow_tasks(id) ON DELETE SET NULL,
    uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, sha256)
);

CREATE TABLE IF NOT EXISTS memory_evidence (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    memory_id TEXT NOT NULL,
    source TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}',
    confidence NUMERIC NOT NULL DEFAULT 1 CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE memories ADD COLUMN IF NOT EXISTS namespace TEXT NOT NULL DEFAULT 'default';
ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding_id TEXT;
ALTER TABLE memories ADD COLUMN IF NOT EXISTS provenance JSONB NOT NULL DEFAULT '{}';
ALTER TABLE memories ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'api';
ALTER TABLE memories ADD COLUMN IF NOT EXISTS confidence NUMERIC NOT NULL DEFAULT 1 CHECK (confidence >= 0 AND confidence <= 1);
ALTER TABLE memories ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','ARCHIVED','DELETED'));
ALTER TABLE memories ADD COLUMN IF NOT EXISTS retention JSONB NOT NULL DEFAULT '{}';
ALTER TABLE memories ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0);
ALTER TABLE memories ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE UNIQUE INDEX IF NOT EXISTS uq_memories_tenant_namespace_id ON memories(tenant_id, namespace, id);

CREATE TABLE IF NOT EXISTS governance_decisions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    risk_score NUMERIC NOT NULL DEFAULT 0 CHECK (risk_score >= 0 AND risk_score <= 1),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','REJECTED','SUPERSEDED')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    decision_id TEXT NOT NULL REFERENCES governance_decisions(id) ON DELETE CASCADE,
    approver_subject TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('APPROVED','REJECTED')),
    reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, decision_id, approver_subject)
);

CREATE TABLE IF NOT EXISTS llm_requests (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    subject TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','SUCCEEDED','FAILED','CANCELLED')),
    idempotency_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS llm_usage (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    request_id TEXT NOT NULL REFERENCES llm_requests(id) ON DELETE CASCADE,
    input_tokens INTEGER NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens INTEGER NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_costs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    request_id TEXT NOT NULL REFERENCES llm_requests(id) ON DELETE CASCADE,
    amount NUMERIC NOT NULL CHECK (amount >= 0),
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sandbox_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    subject TEXT NOT NULL,
    command JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED','TIMED_OUT')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0)
);

CREATE TABLE IF NOT EXISTS sandbox_artifacts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    sandbox_run_id TEXT NOT NULL REFERENCES sandbox_runs(id) ON DELETE CASCADE,
    uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, sandbox_run_id, sha256)
);

CREATE TABLE IF NOT EXISTS research_sources (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    uri TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','ARCHIVED','DELETED')),
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, uri)
);

CREATE TABLE IF NOT EXISTS research_evidence (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL REFERENCES research_sources(id) ON DELETE CASCADE,
    claim TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}',
    confidence NUMERIC NOT NULL DEFAULT 1 CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workflow_tasks_lease ON workflow_tasks(tenant_id, status, lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_workflow_attempts_task ON workflow_attempts(tenant_id, workflow_task_id, attempt_number);
CREATE INDEX IF NOT EXISTS idx_memory_evidence_memory ON memory_evidence(tenant_id, memory_id);
CREATE INDEX IF NOT EXISTS idx_governance_decisions_tenant_status ON governance_decisions(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_audit_events_target ON audit_events(tenant_id, target, created_at);
CREATE INDEX IF NOT EXISTS idx_llm_requests_tenant_created ON llm_requests(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sandbox_runs_tenant_status ON sandbox_runs(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_research_sources_tenant_uri ON research_sources(tenant_id, uri);
