"""Typed public application configuration.

``PublicConfig`` holds only non-secret settings. It may be validated and then
serialized (logs, run records, telemetry resource attributes). Credentials live
in :class:`agentscope.config.secret.SecretConfig` and never appear here.

Since Phase 1A.2 this is a plain, frozen :class:`pydantic.BaseModel`: it is
built programmatically (tests, embedding) or loaded from a typed configuration
file via :func:`agentscope.config.loader.load_public_config`. ``.env`` is
exclusively a local *secret* carrier and is never read here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agentscope.models.configuration import ModelDefinition

__all__ = ["Limits", "ModelSlots", "PublicConfig", "RuntimeMode"]

_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"})


class RuntimeMode(StrEnum):
    """Which sandbox-runtime backend the platform should wire."""

    FAKE = "fake"
    DOCKER = "docker"


class Limits(BaseModel):
    """Resource ceilings applied to model-facing runtime operations."""

    model_config = ConfigDict(frozen=True)

    default_timeout_s: float = Field(default=30.0, gt=0)
    max_output_bytes: int = Field(default=1_000_000, gt=0)


class ModelSlots(BaseModel):
    """The two provider-independent model roles available to architectures."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    regular: ModelDefinition
    fast: ModelDefinition

    @model_validator(mode="after")
    def _fixed_keys(self) -> ModelSlots:
        if self.regular.key != "regular" or self.fast.key != "fast":
            raise ValueError("model definition keys must match their regular/fast slots")
        return self


class PublicConfig(BaseModel):
    """Validated, serializable, non-secret application configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    architecture_key: str | None = None
    models: ModelSlots | None = None
    runtime_mode: RuntimeMode = RuntimeMode.FAKE
    telemetry_enabled: bool = False
    telemetry_endpoint: str | None = None
    log_level: str = "INFO"
    limits: Limits = Limits()

    @field_validator("models", mode="before")
    @classmethod
    def _fill_model_keys(cls, value: Any) -> Any:
        """Inject fixed internal registry keys into the two public slots."""
        if not isinstance(value, dict):
            return value
        filled: dict[str, Any] = {}
        for name, entry in value.items():
            if isinstance(entry, dict):
                if "key" in entry:
                    raise ValueError("model slot configuration must not contain an internal key")
                entry = {**entry, "key": name}
            filled[name] = entry
        return filled

    @field_validator("log_level")
    @classmethod
    def _known_log_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in _LOG_LEVELS:
            raise ValueError(f"log_level must be one of {sorted(_LOG_LEVELS)}, got {value!r}")
        return upper

    @model_validator(mode="after")
    def _endpoint_required_when_telemetry_enabled(self) -> PublicConfig:
        if self.telemetry_enabled and not self.telemetry_endpoint:
            raise ValueError("telemetry_endpoint is required when telemetry_enabled is true")
        return self

    def safe_dump(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot. This object holds no secrets."""
        return self.model_dump(mode="json")
