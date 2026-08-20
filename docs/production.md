# Production Readiness

The platform now exposes runtime production controls shared by every level.

## Controls

- `GET /ready` reports an honest RED/YELLOW/GREEN matrix that combines implementation/catalog checks with critical production-control assessments; it must not be treated as GREEN until durable state, authorization, dependency checks, and sandbox isolation are complete.
- `GET /architecture/readiness` returns the same per-level readiness matrix for architecture inspection.
- `GET /metrics` exports Prometheus-compatible counters and latency summaries from executed level operations.
- `GET /security/policy` exposes the active API-key and rate-limit policy without disclosing secrets.
- The API middleware applies rate limiting and security headers to every response.
- If `AGI_API_KEY` is set, all non-public API routes require `X-API-Key`.

## Required environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `AGI_ENV` | Runtime environment name. | `production` |
| `AGI_SERVICE_NAME` | Service name emitted in headers. | `agi-platform` |
| `AGI_API_KEY` | Optional API key for protected routes. | unset |
| `AGI_RATE_LIMIT_PER_MINUTE` | Per-client API request limit. | `120` |
| `DATABASE_URL` | Postgres/pgvector connection string. | compose Postgres URL |
| `QDRANT_URL` | Qdrant endpoint. | compose Qdrant URL |
| `NEO4J_URI` | Neo4j Bolt URI. | compose Neo4j URI |
| `REDIS_URL` | Redis connection string. | compose Redis URL |


## Real integrations

The runtime no longer fabricates LLM, GitHub, research, or translation responses. Configure these integrations with provider credentials/endpoints:

- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, or `OPENROUTER_API_KEY` for hosted LLM providers.
- `OLLAMA_BASE_URL`, `VLLM_BASE_URL`, or `LM_STUDIO_BASE_URL` for local OpenAI-compatible or Ollama-compatible model servers.
- `GITHUB_TOKEN` for higher GitHub API rate limits when indexing repositories or collecting research evidence.
- `LIBRETRANSLATE_URL` and optional `LIBRETRANSLATE_API_KEY` for Chinese-to-English translation.

When an integration is not configured or a remote API is unavailable, the API returns the real unavailable state instead of generated sample content.

## Production hardening checklist / чеклист посилення

Перед роботою з реальними користувачами перевірте ці controls у production-like середовищі:

- Збирайте та деплойте immutable container images; Kubernetes manifests не мають використовувати `latest` tags.
- Зберігайте provider credentials і database URLs у Kubernetes Secrets або зовнішньому secret manager.
- Зберігайте non-secret runtime settings у ConfigMaps і тримайте environment-specific values поза image.
- Увімкніть readiness, liveness і startup probes для API deployment.
- Задайте CPU/memory requests і limits для кожного container.
- Запускайте containers як non-root там, де це можливо, і drop unnecessary Linux capabilities.
- Підтвердіть, що `/ready` повертає `ready` лише після успішного import усіх level implementations і required dependencies; для production також додайте dependency та capability probes, які виконують реальні операції проти Postgres, Redis, Neo4j, Qdrant і sandbox runtime.
- Підтвердіть, що `/live` лишається lightweight і не залежить від databases або remote providers.
- Налаштуйте dashboards і alerts з `/metrics` перед увімкненням production traffic.
- Зафіксуйте database migrations і перевірте rollback/restore procedures перед deployment.

## Phase 1 security foundation status

`AGI_API_KEYS` can now define scoped tenant API keys as a JSON list. Each item must include `key`, `tenant_id`, and `permissions`; optional fields are `key_id`, `subject`, and `roles`. `AGI_API_KEY` remains supported only as a legacy full-access compatibility key and should not be used for new production deployments.

Protected routes now require an explicit permission when authorization is configured. High-risk routes under `/sandbox`, `/orchestrate`, `/github`, `/graph`, `/governance`, and `/evolution` fail closed when no authorization credentials are configured. API error responses use a canonical sanitized envelope with `error.code`, `error.message`, and `error.request_id`.

Example development-only scoped key configuration:

```json
[
  {
    "key": "replace-with-secret-value",
    "key_id": "svc-platform-admin-1",
    "subject": "platform-admin",
    "tenant_id": "tenant-a",
    "roles": ["admin"],
    "permissions": ["*"]
  }
]
```

## Multi-tenant identity architecture status

The API key control plane now models tenants, users, service accounts, roles, permissions, hashed tenant-bound API keys, revocation, rotation metadata, optional expiration, and an in-process authentication audit trail. Runtime request flow is:

```text
request -> authentication -> identity -> tenant context -> authorization -> tenant-scoped service operation
```

Important invariants:

- API keys are hashed at rest in the runtime identity registry and in the database schema; plaintext keys are accepted only at configuration/bootstrap boundaries.
- The authenticated identity determines the tenant. `X-Tenant-ID` can only narrow the context to that same tenant and cannot switch identity to another tenant.
- Cross-tenant access fails closed during authentication or tenant-scoped repository/service lookup.
- Protected services require an explicit tenant context and tenant-filter memory, graph, workflow, governance, analysis, research, sandbox, GitHub, Chinese-hub, and evolution state.
- API keys can be revoked, expired, and rotated with previous-key metadata during a retirement window.

Remaining security work: the current implementation is still an in-process identity registry. Production must back tenants, users, service accounts, roles, permissions, API keys, and audit events with Postgres repositories, hashed key material, key prefix lookup, online rotation workflows, and centralized policy enforcement.
