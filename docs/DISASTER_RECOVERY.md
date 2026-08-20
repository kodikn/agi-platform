# Disaster Recovery

Backup is necessary but does not make the platform production ready. Production readiness requires automated restore tests and verified application behavior after restore.

## Objectives

| System | RPO | RTO | Frequency | Retention | Encryption | Storage | Access control |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PostgreSQL | 15 minutes | 60 minutes | continuous WAL + daily full | 35 days | KMS envelope encryption | versioned object storage | break-glass DBA + CI restore role |
| Qdrant | 1 hour | 2 hours | hourly snapshots | 14 days | KMS encrypted bucket | object storage | search platform role |
| Neo4j | 1 hour | 2 hours | hourly incremental + daily full | 14 days | KMS encrypted bucket | object storage | graph platform role |
| Redis | 5 minutes if queue/lock state is critical; otherwise best-effort | 30 minutes | AOF replication + daily snapshot | 7 days | encrypted disk/bucket | managed Redis backup | platform SRE role |

## Restore test procedure

1. Create tenant-scoped test data for memory, workflow, graph, and governance records.
2. Run backups for PostgreSQL, Qdrant, Neo4j, and Redis where state is critical.
3. Destroy the test database/state.
4. Restore each dependency into an isolated namespace.
5. Start the application against restored dependencies.
6. Verify critical data exists.
7. Verify tenant isolation with cross-tenant read/write attempts.
8. Verify workflow checkpoint/recovery state.
9. Verify memory search and metadata.

The restore test must run on a schedule and before production release promotion.
