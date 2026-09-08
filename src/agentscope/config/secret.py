"""Typed secret configuration.

``SecretConfig`` is the *only* structured carrier of credentials in AgentScope,
and only :mod:`agentscope.bootstrap` is permitted to consume it. Every field is
a :class:`pydantic.SecretStr`, so values are excluded from ``repr``, ``str``,
``model_dump``, and ``model_dump_json`` by construction.
"""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["MissingSecretError", "SecretConfig"]


class MissingSecretError(RuntimeError):
    """Raised when a required secret was not configured.

    The message names only the field, never a value.
    """


class SecretConfig(BaseSettings):
    """Credentials loaded at bootstrap and handed only to trusted clients."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTSCOPE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    meta_model_api_key: SecretStr | None = None
    phoenix_api_key: SecretStr | None = None
    otlp_headers: SecretStr | None = None

    def require(self, field: str) -> str:
        """Return the plaintext value of ``field`` or raise ``MissingSecretError``."""
        if field not in type(self).model_fields:
            raise MissingSecretError(f"unknown secret field: {field!r}")
        value: SecretStr | None = getattr(self, field)
        if value is None:
            raise MissingSecretError(f"required secret is not configured: {field}")
        return str(value.get_secret_value())

    def safe_dump(self) -> dict[str, str]:
        """Return ``{field: "REDACTED"}`` for configured fields only."""
        return {
            name: "REDACTED" for name in type(self).model_fields if getattr(self, name) is not None
        }
