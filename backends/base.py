from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class BackendError(Exception):
    """Structured backend error with optional retry classification."""

    message: str
    provider: Optional[str] = None
    retriable: bool = False
    status_code: Optional[int] = None
    request_id: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


@dataclass(slots=True)
class CapabilityReport:
    provider: str
    model: Optional[str]
    available: bool
    endpoint: Optional[str] = None
    supports_streaming: bool = False
    supported_features: list[str] = field(default_factory=list)
    notes: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModelState:
    provider: str
    model: Optional[str]
    endpoint: Optional[str]
    model_loaded: bool
    fallback_available: bool
    last_error: Optional[str] = None
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    active_backend: Optional[str] = None


@dataclass(slots=True)
class GenerationResult:
    output: str
    provider: str
    model: Optional[str]
    latency_ms: float
    request_id: Optional[str] = None
    fallback_used: bool = False
    failure_reason: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HealthReport:
    provider: str
    healthy: bool
    model: Optional[str]
    endpoint: Optional[str]
    fallback_available: bool
    last_error: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


class BackendInterface(ABC):
    @abstractmethod
    def detect_capabilities(self) -> CapabilityReport:
        """Return a structured capability report."""

    @abstractmethod
    def generate(self, prompt: str, **params: Any) -> GenerationResult:
        """Generate a response for the provided prompt."""

    @abstractmethod
    def get_state(self) -> ModelState:
        """Return the current backend state."""

    @abstractmethod
    def health(self) -> HealthReport:
        """Return a health report suitable for monitoring."""

    @abstractmethod
    def shutdown(self) -> None:
        """Release any backend resources."""


def dataclass_asdict(value: Any) -> dict[str, Any]:
    try:
        return asdict(value)
    except Exception:
        return {}
