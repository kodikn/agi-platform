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
