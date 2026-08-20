from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx


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
        return self.api_key is not None or (self.name in {"ollama", "vllm", "lm-studio"} and bool(self.base_url))


@dataclass
class LLMCore:
    providers: dict[str, Provider] = field(default_factory=dict)
    cache: dict[str, dict] = field(default_factory=dict)
    usage: list[dict] = field(default_factory=list)
    timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        if not self.providers:
            defaults = (
                Provider("openai", ("gpt-4.1", "gpt-4.1-mini"), 10, os.getenv("OPENAI_BASE_URL", "https://api.openai.com"), "OPENAI_API_KEY"),
                Provider("anthropic", ("claude-3-5-sonnet-latest",), 20, os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"), "ANTHROPIC_API_KEY", "/v1/messages"),
                Provider("gemini", ("gemini-1.5-pro",), 30, os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"), "GEMINI_API_KEY"),
                Provider("openrouter", ("openrouter/auto",), 40, os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api"), "OPENROUTER_API_KEY"),
                Provider("ollama", ("llama3",), 50, os.getenv("OLLAMA_BASE_URL", ""), None, "/api/chat", "/api/embeddings"),
                Provider("vllm", ("vllm-local",), 60, os.getenv("VLLM_BASE_URL", ""), None),
                Provider("lm-studio", ("lm-studio-local",), 70, os.getenv("LM_STUDIO_BASE_URL", ""), None),
            )
            self.providers.update({provider.name: provider for provider in defaults})

    def models(self) -> dict[str, Any]:
        return {
            "providers": {
                name: {"models": provider.models, "configured": provider.configured, "base_url": provider.base_url}
                for name, provider in self.providers.items()
            }
        }

    def route(self, requested_model: str | None = None) -> Provider:
        configured = sorted((p for p in self.providers.values() if p.configured), key=lambda item: item.priority)
        if requested_model:
            for provider in configured:
                if requested_model in provider.models:
                    return provider
        if configured:
            return configured[0]
        raise RuntimeError("no LLM provider is configured; set an API key or local model endpoint")

    def complete(self, message: str, model: str | None = None, stream: bool = False) -> dict[str, Any]:
        started = time.perf_counter()
        provider = self.route(model)
        chosen_model = model or provider.models[0]
        headers = self._headers(provider)
        payload = self._chat_payload(provider, chosen_model, message, stream)
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{provider.base_url.rstrip('/')}{provider.chat_path}", headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        content = self._extract_chat_content(provider, body)
        usage = self._extract_usage(body, message, content)
        record = {
            "provider": provider.name,
            "model": chosen_model,
            "response": content,
            "streaming": stream,
            "tool_calls": body.get("tool_calls", []),
            "usage": usage,
            "metrics": {"latency_ms": round((time.perf_counter() - started) * 1000, 3), "cost": 0.0, "errors": 0},
            "raw_provider_response": body,
        }
        self.usage.append(record)
        return record

    def embeddings(self, text: str, model: str | None = None) -> dict[str, Any]:
        provider = self.route(model)
        chosen_model = model or provider.models[0]
        headers = self._headers(provider)
        payload = {"model": chosen_model, "input": text} if provider.name != "ollama" else {"model": chosen_model, "prompt": text}
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{provider.base_url.rstrip('/')}{provider.embeddings_path}", headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        embedding = body.get("embedding") or body.get("data", [{}])[0].get("embedding")
        if embedding is None:
            raise RuntimeError(f"provider {provider.name} did not return an embedding")
        return {"provider": provider.name, "model": chosen_model, "embedding": embedding, "dimensions": len(embedding)}

    def _headers(self, provider: Provider) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        if provider.name == "anthropic":
            headers["anthropic-version"] = "2023-06-01"
        return headers

    def _chat_payload(self, provider: Provider, model: str, message: str, stream: bool) -> dict[str, Any]:
        if provider.name == "anthropic":
            return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": message}], "stream": stream}
        if provider.name == "ollama":
            return {"model": model, "messages": [{"role": "user", "content": message}], "stream": stream}
        return {"model": model, "messages": [{"role": "user", "content": message}], "stream": stream}

    def _extract_chat_content(self, provider: Provider, body: dict[str, Any]) -> str:
        if provider.name == "anthropic":
            return "".join(part.get("text", "") for part in body.get("content", []))
        if provider.name == "ollama":
            return body.get("message", {}).get("content", "")
        return body.get("choices", [{}])[0].get("message", {}).get("content", "")

    def _extract_usage(self, body: dict[str, Any], prompt: str, completion: str) -> dict[str, int]:
        usage = body.get("usage", {})
        return {
            "input_tokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or len(prompt.split())),
            "output_tokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or len(completion.split())),
        }
