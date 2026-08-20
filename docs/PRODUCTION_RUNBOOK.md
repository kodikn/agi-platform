# Production Runbook

## Rollout

1. Confirm CI, security scans, migration tests, and restore tests pass.
2. Deploy with rolling update (`maxUnavailable=0`, `maxSurge=1`).
3. Watch `/ready`, p95 HTTP latency, HTTP 5xx, Redis errors, DB latency, and provider failures.
4. Abort rollout if readiness fails, canary SLOs fail, or security alerts trigger.

## Incident response

- Rate-limit dependency failure: security-sensitive limits fail closed. Restore Redis or switch traffic to healthy replicas; do not set fail-open in production.
- Database failure: put API in maintenance if `/ready` fails, restore from latest verified backup, then run tenant-isolation and workflow-recovery smoke tests.
- Provider failure: monitor provider failure metrics, fail over configured providers, and verify cost-limit enforcement.
- Suspected secret leak: revoke keys, rotate credentials, run secret scan, review structured logs for redaction gaps.

## Restore validation

After any restore, verify API health, tenant isolation, workflow recovery, memory retrieval, graph reads, and audit continuity before accepting production traffic.
