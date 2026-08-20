# API Documentation

The API exposes concrete endpoints for every platform level.

## Level 0 — LLM Core
- `POST /chat`
- `POST /completion`
- `POST /embeddings`
- `GET /models`

## Level 1 — Memory Layer
- `POST /memory/store`
- `POST /memory/search`
- `POST /memory/retrieve`
- `POST /memory/consolidate`

## Level 2 — Memory Guardian
- `POST /guardian/validate`
- `GET /guardian/audit`

## Level 3 — Research Layer
- `POST /research/query`
- `POST /research/report`

## Level 4 — Chinese Research Hub
- `POST /chinese/articles`
- `POST /chinese/analyze`

## Level 5 — Analysis Layer
- `POST /analyze/code`
- `POST /analyze/repository`

## Level 6 — GitHub Intelligence
- `POST /github/repositories`
- `GET /github/repositories/{owner}/{repo}`

## Level 7 — Sandbox Lab
- `POST /sandbox/execute`

## Level 8 — Knowledge Graph
- `POST /graph/entities`
- `POST /graph/relationships`
- `POST /graph/search`

## Level 9 — Orchestrator
- `POST /orchestrate`
  - Returns a checkpointed workflow graph, crew/role routing, agent handoff trace, zero-code workflow contract, and competitive capability tags adopted from leading multi-agent projects.

## Level 10 — Architecture Governance
- `POST /governance/proposals`
- `POST /governance/reviews`

## Level 11 — Self Improvement
- `POST /evolution/evaluate`
- `POST /evolution/proposals`

## Production Operations
- `GET /ready`
- `GET /architecture/readiness`
- `GET /architecture/competitive-advantages`
- `GET /metrics`
- `GET /security/policy`
