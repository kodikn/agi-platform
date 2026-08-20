# Deployment Guide

## Docker Compose

Run the complete local stack:

```bash
docker compose up --build
```

The API listens on `http://localhost:8000` and depends on Postgres/pgvector, Qdrant, Redis, and Neo4j services.

## Database

Apply SQL migrations from `migrations/` in lexical order. The first migration creates model, provider, usage, memory, GitHub intelligence, and architecture governance tables.

## Kubernetes

The `k8s/` directory contains a minimal API deployment and service that can be extended with managed database endpoints and secrets.

## Environment-specific compose usage

- Development: `docker compose --profile dev up --build` publishes the API and binds Postgres, Redis, Qdrant, and Neo4j to `127.0.0.1` for local tools.
- Staging: use the base compose file with non-default secrets, private networking, and managed service endpoints where possible.
- Production: use `docker compose -f docker-compose.yml -f compose/docker-compose.prod.yml --profile prod up --build` or Kubernetes/managed services. The production override removes published Postgres, Redis, Qdrant, and Neo4j ports; expose only the API through an authenticated ingress or load balancer.

The API container runs as a non-root UID, drops Linux capabilities, uses `no-new-privileges`, and has a read-only root filesystem with a small `/tmp` tmpfs. Redis is required for distributed rate limits and locks by default; set `AGI_RATE_LIMIT_FAIL_OPEN=true` only for non-security-sensitive development experiments.
