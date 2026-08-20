from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from agi_platform.outbound import OutboundPolicy, SecureHTTPClient


@dataclass(frozen=True)
class Provider:
    name: str
    models: tuple[str, ...]
    priority: int
    base_url: str
    api_key_env: str | None = None
    chat_path: str = "/v1/chat/completions"
    embeddings_path: str = "/v1/embeddings"

    @property
    def api_key(self) -> str | None:
        return os.getenv(self.api_key_env) if self.api_key_env else None

    @property
    def configured(self) -> bool:
        return self.api_key is not None or (
            self.name in {"ollama", "vllm", "lm-studio"} and bool(self.base_url)
        )


@dataclass
class ProviderHealth:
    failures: int = 0
    circuit_open_until: float = 0.0
    last_status: str = "unknown"

    def available(self) -> bool:
        return time.monotonic() >= self.circuit_open_until


@dataclass(frozen=True)
class RoutingPolicy:
    max_retries: int = 2
    backoff_seconds: float = 0.05
    circuit_breaker_failures: int = 3
    circuit_breaker_cooldown: float = 30.0
    model_allowlist: frozenset[str] = frozenset()


@dataclass
class CostPolicy:
    max_tokens_per_request: int = 8192
    tenant_budget_usd: float = 1.0
    spent_by_tenant: dict[str, float] = field(default_factory=dict)
    price_per_1k_tokens: float = 0.001

    def estimate(self, tokens_in: int, tokens_out: int) -> float:
        return ((tokens_in + tokens_out) / 1000) * self.price_per_1k_tokens

    def reserve(self, tenant_id: str, estimated_cost: float) -> None:
        if (
            self.spent_by_tenant.get(tenant_id, 0.0) + estimated_cost
            > self.tenant_budget_usd
        ):
            raise RuntimeError("LLM cost budget exceeded")

    def commit(self, tenant_id: str, cost: float) -> None:
        self.spent_by_tenant[tenant_id] = (
            self.spent_by_tenant.get(tenant_id, 0.0) + cost
        )


class ProviderAdapter:
    def __init__(
        self,
        provider: Provider,
        client: SecureHTTPClient | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.provider = provider
        self.client = client or SecureHTTPClient(
            OutboundPolicy(allowed_content_types=frozenset({"application/json"}))
        )
        self.timeout_seconds = timeout_seconds

    def chat(self, model: str, message: str, stream: bool) -> dict[str, Any]:
        response = self.client.post(
            f"{self.provider.base_url.rstrip('/')}{self.provider.chat_path}",
            headers=self._headers(),
            json=self._chat_payload(model, message, stream),
        )
        response.raise_for_status()
        return response.json()

    def embeddings(self, model: str, text: str) -> dict[str, Any]:
        payload = (
            {"model": model, "input": text}
            if self.provider.name != "ollama"
            else {"model": model, "prompt": text}
        )
        response = self.client.post(
            f"{self.provider.base_url.rstrip('/')}{self.provider.embeddings_path}",
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.provider.api_key:
            headers["Authorization"] = f"Bearer {self.provider.api_key}"
        if self.provider.name == "anthropic":
            headers["anthropic-version"] = "2023-06-01"
        return headers

    def _chat_payload(self, model: str, message: str, stream: bool) -> dict[str, Any]:
        if self.provider.name == "anthropic":
            return {
                "model": model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": message}],
                "stream": stream,
            }
        return {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": stream,
        }


class LLMGateway:
    def __init__(
        self,
        providers: dict[str, Provider],
        routing_policy: RoutingPolicy | None = None,
        cost_policy: CostPolicy | None = None,
    ) -> None:
        self.providers = providers
        self.routing_policy = routing_policy or RoutingPolicy()
        self.cost_policy = cost_policy or CostPolicy()
        self.health: dict[str, ProviderHealth] = {
            name: ProviderHealth() for name in providers
        }
        self.usage: list[dict[str, Any]] = []

    def complete(
        self,
        message: str,
        model: str | None = None,
        stream: bool = False,
        tenant_id: str = "legacy",
        request_id: str = "",
    ) -> dict[str, Any]:
        tokens_in = len(message.split())
        if tokens_in > self.cost_policy.max_tokens_per_request:
            raise RuntimeError("LLM token limit exceeded")
        self.cost_policy.reserve(
            tenant_id,
            self.cost_policy.estimate(
                tokens_in, self.cost_policy.max_tokens_per_request
            ),
        )
        errors = 0
        started = time.perf_counter()
        for provider in self._candidate_providers(model):
            chosen_model = model or provider.models[0]
            adapter = ProviderAdapter(provider)
            for attempt in range(self.routing_policy.max_retries + 1):
                try:
                    body = adapter.chat(chosen_model, message, stream)
                    content = self._extract_chat_content(provider, body)
                    if not isinstance(content, str) or not content:
                        raise RuntimeError("malformed LLM response")
                    usage = self._extract_usage(body, message, content)
                    cost = self.cost_policy.estimate(
                        usage["input_tokens"], usage["output_tokens"]
                    )
                    self.cost_policy.reserve(tenant_id, cost)
                    self.cost_policy.commit(tenant_id, cost)
                    self.health[provider.name] = ProviderHealth(last_status="healthy")
                    record = {
                        "provider": provider.name,
                        "model": chosen_model,
                        "request_id": request_id,
                        "tenant_id": tenant_id,
                        "response": content,
                        "streaming": stream,
                        "tool_calls": body.get("tool_calls", []),
                        "usage": usage,
                        "metrics": {
                            "latency_ms": round(
                                (time.perf_counter() - started) * 1000, 3
                            ),
                            "cost": cost,
                            "errors": errors,
                        },
                        "raw_provider_response": body,
                        "status": "succeeded",
                        "timestamp": int(time.time()),
                    }
                    self.usage.append(record)
                    return record
                except httpx.HTTPStatusError as exc:
                    errors += 1
                    if (
                        exc.response.status_code < 500
                        and exc.response.status_code != 429
                    ):
                        self._record_failure(provider.name)
                        break
                    self._sleep(attempt)
                except (
                    httpx.TimeoutException,
                    httpx.TransportError,
                    RuntimeError,
                    ValueError,
                ):
                    errors += 1
                    self._record_failure(provider.name)
                    self._sleep(attempt)
                    if not self.health[provider.name].available():
                        break
        raise RuntimeError("LLM provider unavailable")

    def embeddings(self, text: str, model: str | None = None) -> dict[str, Any]:
        provider = self._candidate_providers(model)[0]
        chosen_model = model or provider.models[0]
        body = ProviderAdapter(provider).embeddings(chosen_model, text)
        embedding = body.get("embedding") or body.get("data", [{}])[0].get("embedding")
        if embedding is None:
            raise RuntimeError(f"provider {provider.name} did not return an embedding")
        return {
            "provider": provider.name,
            "model": chosen_model,
            "embedding": embedding,
            "dimensions": len(embedding),
        }

    def _candidate_providers(self, requested_model: str | None) -> list[Provider]:
        configured = sorted(
            (
                p
                for p in self.providers.values()
                if p.configured and self.health[p.name].available()
            ),
            key=lambda item: item.priority,
        )
        if requested_model:
            if (
                self.routing_policy.model_allowlist
                and requested_model not in self.routing_policy.model_allowlist
            ):
                raise RuntimeError("model is not allowed")
            configured = [p for p in configured if requested_model in p.models]
        if not configured:
            raise RuntimeError(
                "no LLM provider is configured; set an API key or local model endpoint"
            )
        return configured

    def _record_failure(self, provider_name: str) -> None:
        health = self.health[provider_name]
        health.failures += 1
        health.last_status = "unhealthy"
        if health.failures >= self.routing_policy.circuit_breaker_failures:
            health.circuit_open_until = (
                time.monotonic() + self.routing_policy.circuit_breaker_cooldown
            )

    def _sleep(self, attempt: int) -> None:
        if attempt < self.routing_policy.max_retries:
            time.sleep(self.routing_policy.backoff_seconds * (2**attempt))

    def _extract_chat_content(self, provider: Provider, body: dict[str, Any]) -> str:
        if provider.name == "anthropic":
            return "".join(part.get("text", "") for part in body.get("content", []))
        if provider.name == "ollama":
            return body.get("message", {}).get("content", "")
        return body.get("choices", [{}])[0].get("message", {}).get("content", "")

    def _extract_usage(
        self, body: dict[str, Any], prompt: str, completion: str
    ) -> dict[str, int]:
        usage = body.get("usage", {})
        return {
            "input_tokens": int(
                usage.get("prompt_tokens")
                or usage.get("input_tokens")
                or len(prompt.split())
            ),
            "output_tokens": int(
                usage.get("completion_tokens")
                or usage.get("output_tokens")
                or len(completion.split())
            ),
        }


@dataclass
class LLMCore:
    providers: dict[str, Provider] = field(default_factory=dict)
    cache: dict[str, dict] = field(default_factory=dict)
    usage: list[dict] = field(default_factory=list)
    timeout_seconds: float = 20.0
    gateway: LLMGateway | None = None

    def __post_init__(self) -> None:
        if not self.providers:
            defaults = (
                Provider(
                    "openai",
                    ("gpt-4.1", "gpt-4.1-mini"),
                    10,
                    os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
                    "OPENAI_API_KEY",
                ),
                Provider(
                    "anthropic",
                    ("claude-3-5-sonnet-latest",),
                    20,
                    os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
                    "ANTHROPIC_API_KEY",
                    "/v1/messages",
                ),
                Provider(
                    "gemini",
                    ("gemini-1.5-pro",),
                    30,
                    os.getenv(
                        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"
                    ),
                    "GEMINI_API_KEY",
                ),
                Provider(
                    "openrouter",
                    ("openrouter/auto",),
                    40,
                    os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api"),
                    "OPENROUTER_API_KEY",
                ),
                Provider(
                    "ollama",
                    ("llama3",),
                    50,
                    os.getenv("OLLAMA_BASE_URL", ""),
                    None,
                    "/api/chat",
                    "/api/embeddings",
                ),
                Provider(
                    "vllm", ("vllm-local",), 60, os.getenv("VLLM_BASE_URL", ""), None
                ),
                Provider(
                    "lm-studio",
                    ("lm-studio-local",),
                    70,
                    os.getenv("LM_STUDIO_BASE_URL", ""),
                    None,
                ),
            )
            self.providers.update({provider.name: provider for provider in defaults})
        self.gateway = self.gateway or LLMGateway(self.providers)
        self.usage = self.gateway.usage

    def models(self) -> dict[str, Any]:
        return {
            "providers": {
                name: {
                    "models": provider.models,
                    "configured": provider.configured,
                    "base_url": provider.base_url,
                    "health": self.gateway.health[name].last_status
                    if self.gateway
                    else "unknown",
                }
                for name, provider in self.providers.items()
            }
        }

    def route(self, requested_model: str | None = None) -> Provider:
        return (
            self.gateway._candidate_providers(requested_model)[0]
            if self.gateway
            else next(iter(self.providers.values()))
        )

    def complete(
        self, message: str, model: str | None = None, stream: bool = False
    ) -> dict[str, Any]:
        if self.gateway is None:
            self.gateway = LLMGateway(self.providers)
        return self.gateway.complete(message, model, stream)

    def embeddings(self, text: str, model: str | None = None) -> dict[str, Any]:
        if self.gateway is None:
            self.gateway = LLMGateway(self.providers)
        return self.gateway.embeddings(text, model)
