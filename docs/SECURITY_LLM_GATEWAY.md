# LLM Gateway

`LLMGateway` isolates provider adapters from business logic and enforces routing, model allowlists, retry/backoff, retry exhaustion, provider health, circuit breakers, fallback, per-request token limits, tenant budget checks, and usage/cost records. Budget failures fail closed to prevent uncontrolled LLM spend.
