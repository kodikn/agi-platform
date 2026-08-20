# Production Readiness

The platform now exposes runtime production controls shared by every level.

## Controls

- `GET /ready` validates that all twelve levels have importable implementation modules, API surfaces, database ownership, observability metrics, and security controls.
- `GET /architecture/readiness` returns the per-level readiness matrix.
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
