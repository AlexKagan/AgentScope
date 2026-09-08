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

__all__ = ["Limits", "PublicConfig", "RuntimeMode"]

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


class PublicConfig(BaseModel):
    """Validated, serializable, non-secret application configuration."""

    model_config = ConfigDict(frozen=True)

    architecture_key: str | None = None
    primary_model_key: str | None = None
    models: dict[str, ModelDefinition] = Field(default_factory=dict)
    runtime_mode: RuntimeMode = RuntimeMode.FAKE
    telemetry_enabled: bool = False
    telemetry_endpoint: str | None = None
    log_level: str = "INFO"
    limits: Limits = Limits()

    @field_validator("models", mode="before")
    @classmethod
    def _fill_model_keys(cls, value: Any) -> Any:
        """Let the catalog key stand in for an omitted ``key`` in each entry."""
        if not isinstance(value, dict):
            return value
        filled: dict[str, Any] = {}
        for name, entry in value.items():
            if isinstance(entry, dict) and "key" not in entry:
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

    @model_validator(mode="after")
    def _model_catalog_is_consistent(self) -> PublicConfig:
        for key, definition in self.models.items():
            if definition.key != key:
                raise ValueError(
                    f"model catalog key {key!r} does not match definition key {definition.key!r}"
                )
        if self.primary_model_key is not None and self.primary_model_key not in self.models:
            raise ValueError(
                f"primary_model_key {self.primary_model_key!r} is not defined in the model catalog"
            )
        return self

    @property
    def primary_model(self) -> ModelDefinition | None:
        """The selected model definition, or ``None`` when no model is selected."""
        if self.primary_model_key is None:
            return None
        return self.models[self.primary_model_key]

    def safe_dump(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot. This object holds no secrets."""
        return self.model_dump(mode="json")
