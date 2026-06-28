from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass, field
from types import SimpleNamespace
import urllib.error
import urllib.request

import pytest

from backends import (
    BackendError,
    BackendFactory,
    BackendInterface,
    CapabilityReport,
    GenerationResult,
    HealthReport,
    OllamaBackend,
    OpenAIBackend,
    OpenAIFirstBackend,
)
from backends import openai_backend as openai_mod


@dataclass
class FakeUsage:
    input_tokens: int = 11
    output_tokens: int = 7


@dataclass
class FakeOpenAIResponse:
    output_text: str = "planned hunt result"
    id: str = "resp_123"
    usage: FakeUsage = field(default_factory=FakeUsage)
    status: str = "completed"


class RateLimitError(Exception):
    status_code = 429


class TimeoutLikeError(TimeoutError):
    status_code = None


class PermanentRequestError(Exception):
    status_code = 400


class FakeResponses:
    def __init__(self, side_effects: list[object]):
        self.side_effects = list(side_effects)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.side_effects:
            raise AssertionError("No more fake OpenAI responses configured")
        effect = self.side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


class FakeOpenAIClient:
    def __init__(self, side_effects: list[object]):
        self.responses = FakeResponses(side_effects)


class StubBackend(BackendInterface):
    def __init__(self, provider: str, result: GenerationResult | None = None, healthy: bool = True):
        self.provider = provider
        self._result = result or GenerationResult(
            output=f"{provider} output",
            provider=provider,
            model=f"{provider}-model",
            latency_ms=1.0,
        )
        self._healthy = healthy
        self.generate_calls = 0
        self.shutdown_calls = 0

    def detect_capabilities(self) -> CapabilityReport:
        return CapabilityReport(
            provider=self.provider,
            model=self._result.model,
            available=self._healthy,
            endpoint=f"{self.provider}://local",
            supported_features=["stub"],
        )

    def generate(self, prompt: str, **params):
        self.generate_calls += 1
        return self._result

    def get_state(self):
        return SimpleNamespace(
            provider=self.provider,
            model=self._result.model,
            endpoint=f"{self.provider}://local",
            model_loaded=True,
            fallback_available=False,
            last_error=None,
            config_snapshot={},
            active_backend=self.provider,
        )

    def health(self):
        return HealthReport(
            provider=self.provider,
            healthy=self._healthy,
            model=self._result.model,
            endpoint=f"{self.provider}://local",
            fallback_available=False,
        )

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def test_openai_backend_generates_structured_result(monkeypatch):
    client = FakeOpenAIClient([FakeOpenAIResponse()])
    backend = OpenAIBackend(model_name="gpt-5.4-mini", api_key="test-key", client=client)

    result = backend.generate("summarize hunt evidence", max_tokens=64, temperature=0.2)

    assert result.provider == "openai"
    assert result.model == "gpt-5.4-mini"
    assert result.output == "planned hunt result"
    assert result.request_id == "resp_123"
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert result.fallback_used is False
    assert client.responses.calls[0]["model"] == "gpt-5.4-mini"
    assert client.responses.calls[0]["max_output_tokens"] == 64


def test_openai_backend_retries_429_then_succeeds(monkeypatch):
    client = FakeOpenAIClient([RateLimitError("too many requests"), FakeOpenAIResponse()])
    backend = OpenAIBackend(
        model_name="gpt-5.4-mini",
        api_key="test-key",
        client=client,
        max_retries=2,
        backoff_base=0.5,
        backoff_factor=2.0,
        backoff_cap=5.0,
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(openai_mod.time, "sleep", lambda value: sleep_calls.append(value))
    monkeypatch.setattr(openai_mod.random, "random", lambda: 0.0)

    result = backend.generate("retry please")

    assert result.output == "planned hunt result"
    assert len(client.responses.calls) == 2
    assert len(sleep_calls) == 1
    assert 0.44 <= sleep_calls[0] <= 0.46


def test_openai_backend_retries_timeout_then_succeeds(monkeypatch):
    client = FakeOpenAIClient([TimeoutLikeError("timeout"), FakeOpenAIResponse()])
    backend = OpenAIBackend(
        model_name="gpt-5.4-mini",
        api_key="test-key",
        client=client,
        max_retries=1,
        backoff_base=0.25,
        backoff_factor=2.0,
        backoff_cap=1.0,
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(openai_mod.time, "sleep", lambda value: sleep_calls.append(value))
    monkeypatch.setattr(openai_mod.random, "random", lambda: 0.0)

    result = backend.generate("retry timeout")

    assert result.output == "planned hunt result"
    assert len(client.responses.calls) == 2
    assert len(sleep_calls) == 1


def test_openai_backend_does_not_retry_permanent_failure(monkeypatch):
    client = FakeOpenAIClient([PermanentRequestError("bad request")])
    backend = OpenAIBackend(model_name="gpt-5.4-mini", api_key="test-key", client=client, max_retries=3)
    sleep_calls: list[float] = []
    monkeypatch.setattr(openai_mod.time, "sleep", lambda value: sleep_calls.append(value))

    with pytest.raises(BackendError) as excinfo:
        backend.generate("do not retry")

    assert excinfo.value.provider == "openai"
    assert excinfo.value.retriable is False
    assert len(client.responses.calls) == 1
    assert sleep_calls == []


def test_openai_first_backend_falls_back_to_ollama_on_transient_failure():
    primary_client = FakeOpenAIClient([RateLimitError("rate limited")])
    primary = OpenAIBackend(
        model_name="gpt-5.4-mini",
        api_key="test-key",
        client=primary_client,
        max_retries=0,
    )
    fallback_result = GenerationResult(
        output="ollama answer",
        provider="ollama",
        model="qwen3:4b",
        latency_ms=2.0,
    )
    fallback = StubBackend("ollama", result=fallback_result)
    chain = OpenAIFirstBackend(primary=primary, fallback=fallback)

    result = chain.generate("hunt fallback")

    assert result.provider == "ollama"
    assert result.fallback_used is True
    assert result.failure_reason
    assert fallback.generate_calls == 1
    assert chain.get_state().active_backend == "ollama"


def test_health_reporting_for_openai_and_ollama(monkeypatch):
    openai_backend = OpenAIBackend(model_name="gpt-5.4-mini", api_key="test-key", client=FakeOpenAIClient([FakeOpenAIResponse()]))
    assert openai_backend.health().healthy is True

    class FakeUrlopenResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"models": []}).encode("utf-8")

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: FakeUrlopenResponse())
    ollama = OllamaBackend(model_name="qwen3:4b", endpoint="http://127.0.0.1:11434")
    health = ollama.health()
    assert health.healthy is True
    assert health.provider == "ollama"


def test_factory_returns_openai_first_chain_when_configured():
    backend = BackendFactory.create(
        model_name="gpt-5.4-mini",
        openai_api_key="test-key",
        openai_kwargs={"client": FakeOpenAIClient([FakeOpenAIResponse()])},
        ollama_kwargs={"timeout": 1.0},
    )

    assert isinstance(backend, OpenAIFirstBackend)
    assert backend.primary.model_name == "gpt-5.4-mini"
    assert backend.fallback is not None


def test_integration_smoke_skips_without_openai_api_key_or_sdk():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not set")
    if importlib.util.find_spec("openai") is None:
        pytest.skip("openai package is not installed")
    ollama_endpoint = os.getenv("ANCHOR_OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
    try:
        with urllib.request.urlopen(f"{ollama_endpoint.rstrip('/')}/api/tags", timeout=2) as response:
            response.read()
    except (urllib.error.URLError, urllib.error.HTTPError):
        pytest.skip("Ollama is not reachable")

    backend = BackendFactory.create(
        model_name=os.getenv("ANCHOR_OPENAI_MODEL", "gpt-5.4-mini"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        ollama_endpoint=ollama_endpoint,
    )
    health = backend.health()
    assert health.provider == "openai"
