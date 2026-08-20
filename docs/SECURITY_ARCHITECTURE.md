# Security Architecture and Threat Model

## Trust boundaries

- User/API clients are untrusted until authenticated and authorized.
- LLM output is untrusted suggestions, never permissions.
- Retrieved documents, GitHub content, research sources, translated content, and tool output are untrusted data.
- Sandbox workloads are hostile by default.
- Provider credentials, database URLs, tokens, cookies, SSH keys, cloud metadata, and repository secrets are protected assets.

## STRIDE highlights

| Threat | Primary risk | Required controls |
| --- | --- | --- |
| Spoofing | API key reuse impersonates all actors | Actor identity, tenant context, scoped keys, audit events |
| Tampering | In-memory state or JSON workflow file can be lost/overwritten | Transactional persistence, optimistic locking, immutable events |
| Repudiation | In-memory audit disappears on restart | Durable append-only audit/event store |
| Information disclosure | Secrets in env/provider errors/repository content can leak | Redaction, secret scanning, least-privilege prompts, sanitized errors |
| Denial of service | Unbounded requests/workflows/sandbox output/external fetches | Request limits, budgets, concurrency limits, circuit breakers |
| Elevation of privilege | Agent/tool calls lack capability authorization | Tool registry + policy engine + approvals |

## LLM-specific threats

- Prompt injection and indirect prompt injection from retrieved/GitHub/web content.
- Tool injection through model-generated tool arguments.
- Instruction hierarchy attacks that attempt to override system/developer policy.
- Confused deputy actions where an agent uses privileged tools on untrusted content.

Required control: all model output that can trigger execution must pass schema validation, policy validation, authorization, risk classification, and audit logging before execution.

## Sandbox threat model

Current subprocess execution is not production isolation. Production sandboxing requires a non-root container/microVM boundary, network namespace policy, read-only base filesystem, resource quotas, disk quota, secret-free environment, artifact extraction, cleanup, and escape tests.

## API hardening target

Every protected endpoint needs request/response schema, authentication, scoped authorization, request_id/correlation_id, bounded body size, rate limiting/backpressure, canonical error response, and redacted structured logs.
