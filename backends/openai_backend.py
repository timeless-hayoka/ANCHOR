from __future__ import annotations

import importlib
import logging
import os
import random
import time
from dataclasses import asdict
from typing import Any, Optional

from .base import (
    BackendError,
    BackendInterface,
    CapabilityReport,
    GenerationResult,
    HealthReport,
    ModelState,
    dataclass_asdict,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 0.4
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_BACKOFF_CAP = 4.0


def _safe_import(module_name: str):
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None


def _status_code(exc: Exception) -> Optional[int]:
    for attr in ("status_code", "http_status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        value = getattr(response, "status_code", None)
        if isinstance(value, int):
            return value
    return None


def _is_timeout_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return True
    if isinstance(exc, TimeoutError):
        return True
    return False


def _is_transient_error(exc: Exception) -> bool:
    code = _status_code(exc)
    if code in {429, 500, 502, 503, 504}:
        return True
    if _is_timeout_error(exc):
        return True
    name = type(exc).__name__.lower()
    if any(token in name for token in ("rate", "connection", "temporar", "overload", "serviceunavailable")):
        return True
    return False


def _is_permanent_error(exc: Exception) -> bool:
    code = _status_code(exc)
    if code in {400, 401, 403, 404, 409, 422}:
        return True
    name = type(exc).__name__.lower()
    if any(token in name for token in ("authentication", "permission", "badrequest", "invalid", "notfound", "unprocessable")):
        return True
    return False


def _request_id(response: Any) -> Optional[str]:
    for attr in ("request_id", "_request_id", "id"):
        value = getattr(response, attr, None)
        if isinstance(value, str) and value:
            return value
    return None


def _usage_value(usage: Any, *names: str) -> Optional[int]:
    if usage is None:
        return None
    for name in names:
        value = getattr(usage, name, None)
        if isinstance(value, int):
            return value
    return None


def _response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text

    output = getattr(response, "output", None)
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            content = getattr(item, "content", None)
            if isinstance(content, list):
                for chunk in content:
                    chunk_text = getattr(chunk, "text", None)
                    if isinstance(chunk_text, str):
                        parts.append(chunk_text)
            text_value = getattr(item, "text", None)
            if isinstance(text_value, str):
                parts.append(text_value)
        if parts:
            return "".join(parts)

    message = getattr(response, "message", None)
    if isinstance(message, str):
        return message
    return ""


def _finish_reason(response: Any) -> Optional[str]:
    status = getattr(response, "status", None)
    if isinstance(status, str):
        return status
    output = getattr(response, "output", None)
    if isinstance(output, list):
        for item in output:
            finish_reason = getattr(item, "finish_reason", None)
            if isinstance(finish_reason, str):
                return finish_reason
            content = getattr(item, "content", None)
            if isinstance(content, list):
                for chunk in content:
                    finish = getattr(chunk, "finish_reason", None)
                    if isinstance(finish, str):
                        return finish
    return None


class OpenAIBackend(BackendInterface):
    def __init__(
        self,
        model_name: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        client: Any | None = None,
        timeout: float = 60.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        backoff_cap: float = DEFAULT_BACKOFF_CAP,
        fallback_used_default: bool = False,
        **config: Any,
    ):
        self.model_name = model_name or os.getenv("ANCHOR_OPENAI_MODEL", DEFAULT_MODEL)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.endpoint = "https://api.openai.com/v1"
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_factor = backoff_factor
        self.backoff_cap = backoff_cap
        self._fallback_used_default = fallback_used_default
        self._last_error: Optional[str] = None
        self._config = dict(config)
        self._client = client
        self._openai = None
        self._state = ModelState(
            provider="openai",
            model=self.model_name,
            endpoint=self.endpoint,
            model_loaded=False,
            fallback_available=True,
            last_error=None,
            config_snapshot={"timeout": timeout, "max_retries": max_retries, **config},
            active_backend="openai",
        )
        if self._client is None:
            self._openai = _safe_import("openai")
            if self._openai is None:
                raise BackendError("openai package is not installed", provider="openai", retriable=False)
            if not self.api_key:
                raise BackendError("OPENAI_API_KEY is not set", provider="openai", retriable=False)
            try:
                self._client = self._openai.OpenAI(api_key=self.api_key, timeout=self.timeout)
            except Exception as exc:  # pragma: no cover - defensive
                raise BackendError(f"Failed to create OpenAI client: {exc}", provider="openai", retriable=False) from exc
        self._state.model_loaded = True

    def detect_capabilities(self) -> CapabilityReport:
        features = ["responses_api", "structured_output", "function_calling"]
        raw = {
            "model": self.model_name,
            "endpoint": self.endpoint,
            "api_key_present": bool(self.api_key),
            "client_type": type(self._client).__name__ if self._client is not None else None,
        }
        return CapabilityReport(
            provider="openai",
            model=self.model_name,
            available=bool(self._client is not None),
            endpoint=self.endpoint,
            supports_streaming=True,
            supported_features=features,
            notes="OpenAI Responses API backend",
            raw=raw,
        )

    def _build_params(self, params: dict[str, Any]) -> dict[str, Any]:
        payload = dict(params)
        if "max_tokens" in payload and "max_output_tokens" not in payload:
            payload["max_output_tokens"] = payload.pop("max_tokens")
        payload.setdefault("max_output_tokens", 512)
        return payload

    def _invoke(self, prompt: str, params: dict[str, Any]) -> Any:
        client = self._client
        if client is None:
            raise BackendError("OpenAI client is not initialized", provider="openai", retriable=False)
        responses = getattr(client, "responses", None)
        if responses is None or not hasattr(responses, "create"):
            raise BackendError("OpenAI client does not expose responses.create", provider="openai", retriable=False)
        return responses.create(model=self.model_name, input=prompt, **params)

    def generate(self, prompt: str, **params: Any) -> GenerationResult:
        normalized = self._build_params(params)
        start = time.perf_counter()
        attempts = 0
        last_exc: Exception | None = None
        last_transient = False
        last_permanent = False
        while attempts <= self.max_retries:
            attempts += 1
            try:
                response = self._invoke(prompt, normalized)
                latency_ms = (time.perf_counter() - start) * 1000
                usage = getattr(response, "usage", None)
                result = GenerationResult(
                    output=_response_text(response),
                    provider="openai",
                    model=self.model_name,
                    latency_ms=latency_ms,
                    request_id=_request_id(response),
                    fallback_used=self._fallback_used_default,
                    input_tokens=_usage_value(usage, "input_tokens", "prompt_tokens"),
                    output_tokens=_usage_value(usage, "output_tokens", "completion_tokens"),
                    finish_reason=_finish_reason(response),
                    raw_response=dataclass_asdict(response) if hasattr(response, "__dataclass_fields__") else {},
                )
                self._state.last_error = None
                self._log_event("generate", latency_ms, success=True, request_id=result.request_id)
                return result
            except Exception as exc:
                last_exc = exc
                transient = _is_transient_error(exc)
                permanent = _is_permanent_error(exc)
                last_transient = transient
                last_permanent = permanent
                self._last_error = f"{type(exc).__name__}: {exc}"
                self._state.last_error = self._last_error
                latency_ms = (time.perf_counter() - start) * 1000
                self._log_event(
                    "generate_failed",
                    latency_ms,
                    success=False,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    status_code=_status_code(exc),
                    retriable=transient and not permanent,
                    attempt=attempts,
                )
                if permanent or not transient:
                    raise BackendError(
                        self._last_error,
                        provider="openai",
                        retriable=transient and not permanent,
                        status_code=_status_code(exc),
                    ) from exc
                sleep_s = min(self.backoff_cap, self.backoff_base * (self.backoff_factor ** (attempts - 1)))
                sleep_s *= 0.9 + random.random() * 0.2
                time.sleep(sleep_s)
        assert last_exc is not None  # pragma: no cover - control flow guard
        raise BackendError(
            f"{type(last_exc).__name__}: {last_exc}",
            provider="openai",
            retriable=last_transient and not last_permanent,
            status_code=_status_code(last_exc),
        ) from last_exc

    def _log_event(self, event: str, latency_ms: float, **extra: Any) -> None:
        logger.info(
            "backend.%s",
            event,
            extra={
                "backend_event": event,
                "provider": "openai",
                "model": self.model_name,
                "endpoint": self.endpoint,
                "latency_ms": round(latency_ms, 3),
                **extra,
            },
        )

    def get_state(self) -> ModelState:
        return self._state

    def health(self) -> HealthReport:
        healthy = self._client is not None and self._state.last_error is None
        return HealthReport(
            provider="openai",
            healthy=healthy,
            model=self.model_name,
            endpoint=self.endpoint,
            fallback_available=True,
            last_error=self._state.last_error,
            details={"configured": bool(self.api_key or self._client), "state": asdict(self._state)},
        )

    def shutdown(self) -> None:
        self._state.model_loaded = False
        self._log_event("shutdown", 0.0, success=True)


class OpenAIFirstBackend(BackendInterface):
    def __init__(
        self,
        primary: OpenAIBackend,
        fallback: BackendInterface | None = None,
        *,
        fallback_on_failure: bool = True,
    ):
        self.primary = primary
        self.fallback = fallback
        self.fallback_on_failure = fallback_on_failure
        self._active = "openai"
        self._last_error: Optional[str] = None

    def detect_capabilities(self) -> CapabilityReport:
        primary = self.primary.detect_capabilities()
        raw = {"primary": asdict(primary)}
        if self.fallback is not None:
            raw["fallback"] = asdict(self.fallback.detect_capabilities())
        return CapabilityReport(
            provider="openai",
            model=self.primary.model_name,
            available=primary.available,
            endpoint=self.primary.endpoint,
            supports_streaming=primary.supports_streaming,
            supported_features=list(primary.supported_features),
            notes="OpenAI-first chain",
            raw=raw,
        )

    def generate(self, prompt: str, **params: Any) -> GenerationResult:
        try:
            result = self.primary.generate(prompt, **params)
            self._active = "openai"
            self._last_error = None
            return result
        except BackendError as exc:
            self._last_error = str(exc)
            if not self.fallback_on_failure or self.fallback is None or not exc.retriable:
                raise
            fallback_result = self.fallback.generate(prompt, **params)
            fallback_result.fallback_used = True
            fallback_result.failure_reason = str(exc)
            self._active = fallback_result.provider
            return fallback_result

    def get_state(self) -> ModelState:
        state = self.primary.get_state()
        state.active_backend = self._active
        state.fallback_available = self.fallback is not None
        state.last_error = self._last_error or state.last_error
        return state

    def health(self) -> HealthReport:
        primary_health = self.primary.health()
        if primary_health.healthy:
            return primary_health
        if self.fallback is None:
            return primary_health
        fallback_health = self.fallback.health()
        return HealthReport(
            provider="openai",
            healthy=fallback_health.healthy,
            model=self.primary.model_name,
            endpoint=self.primary.endpoint,
            fallback_available=True,
            last_error=primary_health.last_error or fallback_health.last_error,
            details={
                "active_backend": self._active,
                "primary": asdict(primary_health),
                "fallback": asdict(fallback_health),
            },
        )

    def shutdown(self) -> None:
        self.primary.shutdown()
        if self.fallback is not None:
            self.fallback.shutdown()
