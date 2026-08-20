# Observability

The API uses structured JSON logs, Prometheus-compatible metrics from `/metrics`, request IDs, and trace IDs. Logs include correlation fields when known: `request_id`, `trace_id`, `tenant_id`, `actor_id`, `agent_id`, `workflow_id`, `run_id`, and `task_id`.

Sensitive fields (`api_key`, `authorization`, `token`, `password`, `secret`, cookies) are redacted by the JSON formatter. Prompts, private data, API keys, credentials, connection strings, and provider secrets must not be logged.

## Metrics catalog

- HTTP: `http_requests_total`, `http_request_latency_ms`, `http_errors_total`
- LLM: `llm_calls_total`, `llm_latency_ms`, `llm_tokens_total`, `llm_cost_total`, `provider_failures_total`
- Workflow: `workflow_duration_ms`, `workflow_failures_total`, `task_retries_total`
- Sandbox: `sandbox_executions_total`, `sandbox_failures_total`
- Memory/DB/Redis/queues: `memory_latency_ms`, `db_latency_ms`, `redis_latency_ms`, `queue_depth`

## Dashboards

Production dashboards should include: API SLO (availability and p95 latency), dependency health (Postgres/Qdrant/Neo4j/Redis), LLM spend/tokens/provider failures, workflow success and duration, sandbox failures, memory latency, queue depth, and Kubernetes saturation (CPU/memory/HPA replicas/restarts).

`/live` reports process health only. `/ready` reports production readiness/dependency posture and may be `not-ready` while `/live` remains healthy.
