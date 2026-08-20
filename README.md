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
cp .env.example .env
docker compose up --build
```

Compose starts the API plus Postgres/pgvector, Qdrant, Redis, and Neo4j. The checked-in `.env.example` contains local-only placeholders; set strong `POSTGRES_PASSWORD` and `NEO4J_PASSWORD` values before using the stack outside a private development machine.

## Implemented levels

- Level 0: LLM provider/model registry, routing, completion, embeddings, caching, and usage metrics.
- Level 1: memory storage, search ranking, retrieval, and consolidation.
- Level 2: memory validation, duplicate risk review, versioning, rollback, and audit.
- Level 3: evidence collection, trust ranking, IOC extraction, and reporting.
- Level 4: Chinese ingestion, configured LibreTranslate-based translation, classification, IOC extraction, and enrichment records.
- Level 5: static code and repository analysis with security findings.
- Level 6: GitHub repository indexing, dependency inventory, and knowledge extraction.
- Level 7: policy-restricted sandbox execution with workspace isolation, scrubbed environment, process resource limits, timeout handling, and metrics.
- Level 8: entity/relationship knowledge graph operations and search.
- Level 9: multi-agent workflow planning, routing, checkpointing, and recovery-ready state.
- Level 10: architecture proposals, risk scoring, decisions, reviews, and approvals.
- Level 11: telemetry evaluation and automatic improvement proposals.


## Best-of-breed capabilities

The orchestrator adopts strengths from leading open-source agent projects: LangGraph-style workflow graphs and recovery checkpoints, CrewAI-style crews/flows, AutoGen-style agent handoff traces, AutoGPT-style extensibility hooks, MetaGPT-style SOP roles, ChatDev-style zero-code contracts, and FastAPI/LangGraph-template production backend controls. Use `GET /architecture/competitive-advantages` to inspect the adopted capability catalog.

## Documentation

- [Architecture](docs/architecture.md)
- [API](docs/api.md)
- [Deployment](docs/deployment.md)
- [Production readiness](docs/production.md)

## Production endpoints

- `GET /ready` reports an honest RED/YELLOW/GREEN production-control matrix; the current prototype intentionally reports `not-ready` until critical durability, authorization, dependency, and sandbox controls are implemented.
- `GET /metrics` exposes Prometheus-compatible metrics.
- `GET /security/policy` reports the active API-key and rate-limit policy.

## Tests

```bash
pytest
```

### Compose environments

Use `docker compose --profile dev up --build` for local development. For production-like compose, use `docker compose -f docker-compose.yml -f compose/docker-compose.prod.yml --profile prod up --build`; the production override does not publish PostgreSQL, Redis, Qdrant, or Neo4j ports.
