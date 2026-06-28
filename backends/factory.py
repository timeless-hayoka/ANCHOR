from __future__ import annotations

import logging
import os
from dataclasses import asdict
from typing import Any, Optional

from .base import BackendInterface, BackendError
from .ollama_backend import DEFAULT_ENDPOINT as OLLAMA_DEFAULT_ENDPOINT
from .ollama_backend import DEFAULT_MODEL as OLLAMA_DEFAULT_MODEL
from .ollama_backend import OllamaBackend
from .openai_backend import DEFAULT_MODEL as OPENAI_DEFAULT_MODEL
from .openai_backend import OpenAIBackend, OpenAIFirstBackend

logger = logging.getLogger(__name__)


class BackendFactory:
    @staticmethod
    def create(
        model_name: Optional[str] = None,
        *,
        openai_api_key: Optional[str] = None,
        openai_model: Optional[str] = None,
        ollama_model: Optional[str] = None,
        ollama_endpoint: Optional[str] = None,
        prefer_openai: bool = True,
        fallback_to_ollama: bool = True,
        logger_: logging.Logger | None = None,
        openai_kwargs: dict[str, Any] | None = None,
        ollama_kwargs: dict[str, Any] | None = None,
    ) -> BackendInterface:
        backend_logger = logger_ or logger
        openai_kwargs = dict(openai_kwargs or {})
        ollama_kwargs = dict(ollama_kwargs or {})

        resolved_openai_model = openai_model or model_name or os.getenv("ANCHOR_OPENAI_MODEL", OPENAI_DEFAULT_MODEL)
        resolved_ollama_model = ollama_model or os.getenv("ANCHOR_OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)
        resolved_ollama_endpoint = ollama_endpoint or os.getenv("ANCHOR_OLLAMA_ENDPOINT", OLLAMA_DEFAULT_ENDPOINT)

        primary = None
        fallback = None
        fallback_reason = None

        if prefer_openai:
            try:
                primary = OpenAIBackend(
                    resolved_openai_model,
                    api_key=openai_api_key,
                    fallback_used_default=False,
                    **openai_kwargs,
                )
            except BackendError as exc:
                fallback_reason = str(exc)
                backend_logger.warning(
                    "backend.factory_openai_unavailable",
                    extra={
                        "backend_event": "factory_openai_unavailable",
                        "provider": "openai",
                        "model": resolved_openai_model,
                        "reason": fallback_reason,
                    },
                )

        if primary is None:
            if not fallback_to_ollama:
                raise BackendError(f"OpenAI backend unavailable: {fallback_reason or 'unknown reason'}", provider="openai")
            fallback = OllamaBackend(
                resolved_ollama_model,
                endpoint=resolved_ollama_endpoint,
                fallback_used_default=True,
                **ollama_kwargs,
            )
            backend_logger.info(
                "backend.factory_selected",
                extra={
                    "backend_event": "factory_selected",
                    "selected_provider": "ollama",
                    "model": resolved_ollama_model,
                    "endpoint": resolved_ollama_endpoint,
                    "fallback_reason": fallback_reason or "openai unavailable",
                },
            )
            return fallback

        if fallback_to_ollama:
            fallback = OllamaBackend(
                resolved_ollama_model,
                endpoint=resolved_ollama_endpoint,
                fallback_used_default=True,
                **ollama_kwargs,
            )
        chain = OpenAIFirstBackend(primary=primary, fallback=fallback, fallback_on_failure=fallback is not None)
        backend_logger.info(
            "backend.factory_selected",
            extra={
                "backend_event": "factory_selected",
                "selected_provider": "openai",
                "model": resolved_openai_model,
                "fallback_enabled": fallback is not None,
                "openai_state": asdict(primary.get_state()),
            },
        )
        return chain


def create_backend(
    model_name: Optional[str] = None,
    *,
    openai_api_key: Optional[str] = None,
    openai_model: Optional[str] = None,
    ollama_model: Optional[str] = None,
    ollama_endpoint: Optional[str] = None,
    prefer_openai: bool = True,
    fallback_to_ollama: bool = True,
    logger_: logging.Logger | None = None,
    openai_kwargs: dict[str, Any] | None = None,
    ollama_kwargs: dict[str, Any] | None = None,
) -> BackendInterface:
    return BackendFactory.create(
        model_name=model_name,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        ollama_model=ollama_model,
        ollama_endpoint=ollama_endpoint,
        prefer_openai=prefer_openai,
        fallback_to_ollama=fallback_to_ollama,
        logger_=logger_,
        openai_kwargs=openai_kwargs,
        ollama_kwargs=ollama_kwargs,
    )

