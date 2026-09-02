"""Public model-identifier parsing.

A model identifier is public configuration of the form ``provider:name`` (for
example ``openai:gpt-x``). It never carries credentials; the matching API key
belongs only to :class:`agentscope.config.secret.SecretConfig`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["ModelIdentifier", "parse_model_identifier"]

# Heuristic: reject values that look like they smuggle a credential rather than
# name a model. Long opaque tokens and the common ``sk-`` prefix are refused.
_CREDENTIAL_HINT = re.compile(r"(sk-[A-Za-z0-9]{8,}|[A-Za-z0-9_\-]{32,})")


@dataclass(frozen=True, slots=True)
class ModelIdentifier:
    """A parsed ``provider:name`` model identifier (public, non-secret)."""

    provider: str
    name: str

    def __str__(self) -> str:
        return f"{self.provider}:{self.name}"


def parse_model_identifier(value: str) -> ModelIdentifier:
    """Parse ``provider:name`` into a :class:`ModelIdentifier`.

    Raises:
        ValueError: if the value is not exactly one non-empty provider and one
            non-empty name separated by a single colon, if it contains
            whitespace, or if either half looks like an embedded credential.
    """
    if not isinstance(value, str):  # pragma: no cover - defensive
        raise ValueError("model identifier must be a string")
    if value != value.strip() or any(ch.isspace() for ch in value):
        raise ValueError(f"model identifier must not contain whitespace: {value!r}")
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"model identifier must be 'provider:name', got {value!r}")
    provider, name = parts
    if not provider or not name:
        raise ValueError(f"model identifier has an empty half: {value!r}")
    if _CREDENTIAL_HINT.fullmatch(provider) or _CREDENTIAL_HINT.fullmatch(name):
        raise ValueError(
            "model identifier looks like it embeds a credential; API keys belong in SecretConfig"
        )
    return ModelIdentifier(provider=provider, name=name)
