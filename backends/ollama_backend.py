from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from typing import Any, Optional

from .base import BackendError, BackendInterface, CapabilityReport, GenerationResult, HealthReport, ModelState

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen3:4b"
DEFAULT_ENDPOINT = "http://127.0.0.1:11434"


class OllamaBackend(BackendInterface):
    def __init__(
        self,
        model_name: Optional[str] = None,
        *,
        endpoint: Optional[str] = None,
        timeout: float = 60.0,
        fallback_used_default: bool = False,
        **config: Any,
    ):
        self.model_name = model_name or os.getenv("ANCHOR_OLLAMA_MODEL", DEFAULT_MODEL)
        self.endpoint = endpoint or os.getenv("ANCHOR_OLLAMA_ENDPOINT", DEFAULT_ENDPOINT)
        self.timeout = timeout
        self._fallback_used_default = fallback_used_default
        self._last_error: Optional[str] = None
        self._state = ModelState(
            provider="ollama",
            model=self.model_name,
            endpoint=self.endpoint,
            model_loaded=True,
            fallback_available=False,
            last_error=None,
            config_snapshot={"timeout": timeout, **config},
            active_backend="ollama",
        )

    def detect_capabilities(self) -> CapabilityReport:
        return CapabilityReport(
            provider="ollama",
            model=self.model_name,
            available=True,
            endpoint=self.endpoint,
            supports_streaming=False,
            supported_features=["chat", "generate", "local_fallback"],
            notes="Local Ollama fallback backend",
            raw={"endpoint": self.endpoint, "model": self.model_name},
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.endpoint.rstrip('/')}{path}"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            raise BackendError(
                f"Ollama request failed with HTTP {exc.code}: {body or exc.reason}",
                provider="ollama",
                retriable=exc.code in {408, 429, 500, 502, 503, 504},
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise BackendError(
                f"Ollama network error: {exc.reason}",
                provider="ollama",
                retriable=True,
            ) from exc

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{self.endpoint.rstrip('/')}{path}"
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            raise BackendError(
                f"Ollama request failed with HTTP {exc.code}: {body or exc.reason}",
                provider="ollama",
                retriable=exc.code in {408, 429, 500, 502, 503, 504},
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise BackendError(
                f"Ollama network error: {exc.reason}",
                provider="ollama",
                retriable=True,
            ) from exc

    def generate(self, prompt: str, **params: Any) -> GenerationResult:
        start = time.perf_counter()
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
        }
        if params:
            options = dict(params)
            if "max_tokens" in options and "num_predict" not in options:
                options["num_predict"] = options.pop("max_tokens")
            payload["options"] = options
        response = self._post("/api/generate", payload)
        latency_ms = (time.perf_counter() - start) * 1000
        result = GenerationResult(
            output=str(response.get("response", "")),
            provider="ollama",
            model=self.model_name,
            latency_ms=latency_ms,
            request_id=str(response.get("id")) if response.get("id") is not None else None,
            fallback_used=self._fallback_used_default,
            input_tokens=response.get("prompt_eval_count"),
            output_tokens=response.get("eval_count"),
            finish_reason=response.get("done_reason") or ("stop" if response.get("done") else None),
            raw_response=response,
        )
        self._state.last_error = None
        logger.info(
            "backend.generate",
            extra={
                "backend_event": "generate",
                "provider": "ollama",
                "model": self.model_name,
                "endpoint": self.endpoint,
                "latency_ms": round(latency_ms, 3),
                "success": True,
                "fallback_used": result.fallback_used,
                "state": asdict(self._state),
            },
        )
        return result

    def get_state(self) -> ModelState:
        return self._state

    def health(self) -> HealthReport:
        start = time.perf_counter()
        try:
            tags = self._get("/api/tags")
            latency_ms = (time.perf_counter() - start) * 1000
            return HealthReport(
                provider="ollama",
                healthy=True,
                model=self.model_name,
                endpoint=self.endpoint,
                fallback_available=False,
                last_error=None,
                details={"latency_ms": round(latency_ms, 3), "response": tags},
            )
        except BackendError as exc:
            return HealthReport(
                provider="ollama",
                healthy=False,
                model=self.model_name,
                endpoint=self.endpoint,
                fallback_available=False,
                last_error=str(exc),
                details={"status_code": exc.status_code, "retriable": exc.retriable},
            )

    def shutdown(self) -> None:
        self._state.model_loaded = False
        logger.info(
            "backend.shutdown",
            extra={
                "backend_event": "shutdown",
                "provider": "ollama",
                "model": self.model_name,
                "endpoint": self.endpoint,
                "state": asdict(self._state),
            },
        )
