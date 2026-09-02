"""Typed public application configuration.

``PublicConfig`` holds only non-secret settings. It may be validated and then
serialized (logs, run records, telemetry resource attributes). Credentials live
in :class:`agentscope.config.secret.SecretConfig` and never appear here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agentscope.config.models import ModelIdentifier, parse_model_identifier

__all__ = ["Limits", "PublicConfig", "RuntimeMode"]

_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"})


class RuntimeMode(StrEnum):
    """Which sandbox-runtime backend the platform should wire.

    Only ``FAKE`` is usable in Phase 0; ``DOCKER`` is reserved for Phase 1A.
    """

    FAKE = "fake"
    DOCKER = "docker"


class Limits(BaseModel):
    """Resource ceilings applied to model-facing runtime operations."""

    model_config = {"frozen": True}

    default_timeout_s: float = Field(default=30.0, gt=0)
    max_output_bytes: int = Field(default=1_000_000, gt=0)


class PublicConfig(BaseSettings):
    """Validated, serializable, non-secret application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTSCOPE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    architecture_key: str | None = None
    primary_model: str | None = None
    runtime_mode: RuntimeMode = RuntimeMode.FAKE
    telemetry_enabled: bool = False
    telemetry_endpoint: str | None = None
    log_level: str = "INFO"
    limits: Limits = Limits()

    @field_validator("log_level")
    @classmethod
    def _known_log_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in _LOG_LEVELS:
            raise ValueError(f"log_level must be one of {sorted(_LOG_LEVELS)}, got {value!r}")
        return upper

    @field_validator("primary_model")
    @classmethod
    def _valid_model_identifier(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        parse_model_identifier(value)  # raises ValueError on bad input
        return value

    @model_validator(mode="after")
    def _endpoint_required_when_telemetry_enabled(self) -> PublicConfig:
        if self.telemetry_enabled and not self.telemetry_endpoint:
            raise ValueError("telemetry_endpoint is required when telemetry_enabled is true")
        return self

    @property
    def model_identifier(self) -> ModelIdentifier | None:
        """The parsed ``primary_model``, or ``None`` when unset."""
        if not self.primary_model:
            return None
        return parse_model_identifier(self.primary_model)

    def safe_dump(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot. This object holds no secrets."""
        return self.model_dump(mode="json")
