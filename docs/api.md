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

## Tool and Agent Integration
- `GET /tools`
  - Returns versionable tool contracts with level ownership, input/output schemas, permissions, side-effect flags, and risk classes.
- `GET /mcp/manifest`
  - Returns an MCP-compatible tool manifest that agents can use to discover approved platform capabilities.

## Production Operations
- `GET /ready`
- `GET /architecture/readiness`
- `GET /architecture/competitive-advantages`
- `GET /metrics`
- `GET /security/policy`

## Tenant identity headers

Protected endpoints require `X-API-Key`. The authenticated API key determines the tenant identity. Clients may send `X-Tenant-ID` only to narrow the request to the same tenant; a mismatched tenant header is rejected with `401` and cannot switch identity across tenants.

API keys are tenant-bound, scoped, revocable, rotatable, and may expire. Operators must store only API key hashes in persistent storage and retain plaintext only at issuance time.
