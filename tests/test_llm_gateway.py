import os

import httpx
import pytest

from agi_platform.llm.core import CostPolicy, LLMGateway, Provider, RoutingPolicy


def provider(name="p", priority=1):
    return Provider(name, ("m",), priority, f"https://{name}.example", "API_KEY")


def test_budget_exceeded_fails_closed():
    gw = LLMGateway({"p": provider("p")}, cost_policy=CostPolicy(tenant_budget_usd=0.0))
    with pytest.raises(RuntimeError, match="budget"):
        gw.complete("hello", "m")


def test_circuit_breaker_after_retry_exhaustion(monkeypatch):
    os.environ["API_KEY"] = "x"
    from agi_platform.llm import core

    class FailingAdapter:
        def __init__(self, provider):
            self.provider = provider

        def chat(self, model, message, stream):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(core, "ProviderAdapter", FailingAdapter)
    gw = LLMGateway(
        {"p": provider("p")},
        RoutingPolicy(
            max_retries=0, circuit_breaker_failures=1, circuit_breaker_cooldown=60
        ),
    )
    with pytest.raises(RuntimeError):
        gw.complete("hello", "m")
    assert not gw.health["p"].available()


def test_fallback_after_500(monkeypatch):
    os.environ["API_KEY"] = "x"
    from agi_platform.llm import core

    class Adapter:
        def __init__(self, provider):
            self.provider = provider

        def chat(self, model, message, stream):
            if self.provider.name == "p1":
                raise httpx.HTTPStatusError(
                    "bad",
                    request=httpx.Request("POST", "https://p1.example"),
                    response=httpx.Response(500),
                )
            return {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    monkeypatch.setattr(core, "ProviderAdapter", Adapter)
    gw = LLMGateway(
        {"p1": provider("p1", 1), "p2": provider("p2", 2)}, RoutingPolicy(max_retries=0)
    )
    assert gw.complete("hello", "m")["provider"] == "p2"


def test_malformed_response_and_model_allowlist(monkeypatch):
    os.environ["API_KEY"] = "x"
    from agi_platform.llm import core

    class BadAdapter:
        def __init__(self, provider):
            self.provider = provider

        def chat(self, model, message, stream):
            return {"bad": True}

    monkeypatch.setattr(core, "ProviderAdapter", BadAdapter)
    gw = LLMGateway(
        {"p": provider("p")},
        RoutingPolicy(max_retries=0, model_allowlist=frozenset({"m"})),
    )
    with pytest.raises(RuntimeError):
        gw.complete("hello", "m")
    with pytest.raises(RuntimeError, match="not allowed"):
        gw.complete("hello", "other")
