from __future__ import annotations

"""Compatibility shim for the new backend package."""

from backends import (  # noqa: F401
    BackendError,
    BackendFactory,
    BackendInterface,
    CapabilityReport,
    GenerationResult,
    HealthReport,
    ModelState,
    OllamaBackend,
    OpenAIBackend,
    OpenAIFirstBackend,
    create_backend,
)

__all__ = [
    "BackendError",
    "BackendFactory",
    "BackendInterface",
    "CapabilityReport",
    "GenerationResult",
    "HealthReport",
    "ModelState",
    "OllamaBackend",
    "OpenAIBackend",
    "OpenAIFirstBackend",
    "create_backend",
]

