# AGI Platform

Production-oriented multi-agent platform organized into twelve executable implementation levels: LLM Core, Memory, Guardian, Research, Chinese Research Hub, Analysis, GitHub Intelligence, Sandbox, Knowledge Graph, Orchestrator, Governance, and Self Improvement.

## Quick start

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Open `http://localhost:8000/docs` for the OpenAPI interface.

## Docker Compose

```bash
docker compose up --build
```

Compose starts the API plus Postgres/pgvector, Qdrant, Redis, and Neo4j.

## Implemented levels

- Level 0: LLM provider/model registry, routing, completion, embeddings, caching, and usage metrics.
- Level 1: memory storage, search ranking, retrieval, and consolidation.
- Level 2: memory validation, duplicate risk review, versioning, rollback, and audit.
- Level 3: evidence collection, trust ranking, IOC extraction, and reporting.
- Level 4: Chinese ingestion, configured LibreTranslate-based translation, classification, IOC extraction, and enrichment records.
- Level 5: static code and repository analysis with security findings.
- Level 6: GitHub repository indexing, dependency inventory, and knowledge extraction.
- Level 7: policy-restricted sandbox execution with workspace isolation and metrics.
- Level 8: entity/relationship knowledge graph operations and search.
- Level 9: multi-agent workflow planning, routing, checkpointing, and recovery-ready state.
- Level 10: architecture proposals, risk scoring, decisions, reviews, and approvals.
- Level 11: telemetry evaluation and automatic improvement proposals.

## Documentation

- [Architecture](docs/architecture.md)
- [API](docs/api.md)
- [Deployment](docs/deployment.md)
- [Production readiness](docs/production.md)

## Production endpoints

- `GET /ready` verifies every level has implementation, API, schema, metrics, and security controls.
- `GET /metrics` exposes Prometheus-compatible metrics.
- `GET /security/policy` reports the active API-key and rate-limit policy.

## Tests

```bash
pytest
```
