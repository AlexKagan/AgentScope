"""Model definitions, declared capabilities, and built-in provider profiles.

A :class:`ModelDefinition` is a validated, frozen, safely serializable record.
It names a credential by symbolic field only, pins or validates its endpoint,
declares the capabilities it needs now, and can produce a credential-free
:class:`~agentscope.models.identity.SafeModelIdentity` plus a reproducibility
fingerprint.

Provider profiles are hard-coded here (no database, no live discovery). Each
profile pins an HTTPS base URL, the credential field its provider uses, and an
explicit allowlist of safe provider request options.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agentscope.models._immutability import canonical_json_value, deep_freeze
from agentscope.models.cost import PriceCard
from agentscope.models.errors import ModelConfigurationError
from agentscope.models.identity import ProviderProfile, SafeModelIdentity, fingerprint

__all__ = [
    "ALLOWED_CREDENTIAL_REFS",
    "BUILTIN_PROVIDER_PROFILES",
    "Capability",
    "ModelDefinition",
    "ModelParameters",
    "ReasoningConfig",
    "ReasoningMode",
    "validate_endpoint",
]

# Symbolic SecretConfig fields a model definition may reference. Kept in sync
# with agentscope.config.secret.SecretConfig by a unit test.
ALLOWED_CREDENTIAL_REFS = frozenset({"openai_api_key", "openrouter_api_key", "meta_model_api_key"})

_SAFE_INVOCATION_OPTIONS = frozenset({"temperature", "top_p", "max_tokens", "seed", "stop"})
_SAFE_PROVIDER_OPTIONS = frozenset(
    {"frequency_penalty", "presence_penalty", "logprobs", "top_logprobs", "parallel_tool_calls"}
)
_REASONING_EFFORTS = frozenset({"none", "minimal", "low", "medium", "high", "xhigh", "max"})
_VERBOSITY_LEVELS = frozenset({"low", "medium", "high"})
_CREDENTIAL_SHAPE = re.compile(r"(?:sk-|LLM\|)[A-Za-z0-9_|-]{8,}")

BUILTIN_PROVIDER_PROFILES: dict[str, ProviderProfile] = {
    "meta": ProviderProfile(
        provider="meta",
        protocol="openai_chat_completions",
        base_url="https://api.meta.ai/v1",
        credential_ref="meta_model_api_key",
        allowed_provider_options=_SAFE_PROVIDER_OPTIONS,
    ),
    "openrouter": ProviderProfile(
        provider="openrouter",
        protocol="openai_chat_completions",
        base_url="https://openrouter.ai/api/v1",
        credential_ref="openrouter_api_key",
        allowed_provider_options=_SAFE_PROVIDER_OPTIONS,
        authoritative_cost_source="openrouter_usage",
    ),
}


class Capability(StrEnum):
    """A behavior a model definition can declare it requires now."""

    TEXT = "text"
    TOOL_CALLING = "tool_calling"
    REASONING = "reasoning"


class ReasoningMode(StrEnum):
    """Canonical reasoning intent; adapters own provider-specific translation."""

    PROVIDER_DEFAULT = "provider_default"
    DISABLED = "disabled"
    ENABLED = "enabled"


class ModelParameters(BaseModel):
    """Portable inference parameters shared across provider adapters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = Field(default=None, gt=0)
    seed: int | None = None
    stop: str | None = None
    verbosity: str | None = None

    @field_validator("temperature", "top_p", mode="before")
    @classmethod
    def _finite_number(cls, value: Any) -> Any:
        if isinstance(value, bool) or (
            value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value))
        ):
            raise ValueError("parameter must be a finite number")
        return value

    @field_validator("max_output_tokens", "seed", mode="before")
    @classmethod
    def _integer_not_boolean(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("integer parameter must not be a boolean")
        return value

    @field_validator("verbosity")
    @classmethod
    def _known_verbosity(cls, value: str | None) -> str | None:
        if value is not None and value not in _VERBOSITY_LEVELS:
            raise ValueError(f"verbosity must be one of {sorted(_VERBOSITY_LEVELS)}")
        return value

    def supplied(self) -> dict[str, str | int | float]:
        """Return only explicitly supplied, non-null portable overrides."""
        return self.model_dump(exclude_none=True, exclude_unset=True)


class ReasoningConfig(BaseModel):
    """Provider-neutral reasoning selection with explicit default semantics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: ReasoningMode = ReasoningMode.PROVIDER_DEFAULT
    effort: str | None = None
    max_tokens: int | None = Field(default=None, gt=0)
    exclude: bool = False

    @field_validator("max_tokens", mode="before")
    @classmethod
    def _token_budget_not_boolean(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("reasoning max_tokens must not be a boolean")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> ReasoningConfig:
        if self.effort is not None and self.effort not in _REASONING_EFFORTS - {"none"}:
            raise ValueError(
                f"reasoning effort must be one of {sorted(_REASONING_EFFORTS - {'none'})}"
            )
        if self.mode is not ReasoningMode.ENABLED and (
            self.effort is not None or self.max_tokens is not None or self.exclude
        ):
            raise ValueError("reasoning details require mode='enabled'")
        if self.mode is ReasoningMode.ENABLED and (self.effort is None) == (
            self.max_tokens is None
        ):
            raise ValueError("enabled reasoning requires exactly one of effort or max_tokens")
        return self

    def supplied(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude_none=True)


def validate_endpoint(url: str, *, allow_http: bool = False) -> str:
    """Return ``url`` unchanged if it is a safe model endpoint, else raise.

    Rejects embedded credentials (user-info), query-string secrets, fragments,
    relative-path traversal, and non-HTTPS schemes (unless ``allow_http``).
    """
    parts = urlsplit(url)
    if parts.scheme == "https" or (allow_http and parts.scheme == "http"):
        pass
    else:
        raise ModelConfigurationError(
            f"model endpoint must use https{' or http' if allow_http else ''}: {url!r}"
        )
    if not parts.hostname:
        raise ModelConfigurationError(f"model endpoint has no host: {url!r}")
    if parts.username or parts.password:
        raise ModelConfigurationError("model endpoint must not embed credentials")
    if parts.query:
        raise ModelConfigurationError("model endpoint must not carry a query string")
    if parts.fragment:
        raise ModelConfigurationError("model endpoint must not carry a fragment")
    if ".." in parts.path.split("/"):
        raise ModelConfigurationError("model endpoint path must not contain '..'")
    return url


class ModelDefinition(BaseModel):
    """A validated, frozen, credential-free model configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(pattern=r"^[a-z][a-z0-9-]*$", exclude=True)
    provider: str
    protocol: str = "openai_chat_completions"
    model_name: str = Field(min_length=1)
    endpoint: str | None = None
    credential_ref: str
    timeout_s: float = Field(default=60.0, gt=0)
    capabilities: tuple[Capability, ...] = (Capability.TEXT, Capability.TOOL_CALLING)
    parameters: ModelParameters = Field(default_factory=ModelParameters)
    reasoning: ReasoningConfig = Field(default_factory=ReasoningConfig)
    provider_options: Mapping[str, Any] = Field(default_factory=dict)
    pricing: PriceCard | None = None
    adapter_version: str = "1.0.0"
    tool_schema_version: str = "1.0.0"
    allow_insecure_http: bool = False

    @field_validator("model_name")
    @classmethod
    def _safe_model_name(cls, value: str) -> str:
        if value != value.strip() or any(char.isspace() for char in value):
            raise ModelConfigurationError("model_name must not contain whitespace")
        if _CREDENTIAL_SHAPE.search(value):
            raise ModelConfigurationError("model_name looks like an embedded credential")
        return value

    @model_validator(mode="after")
    def _validate(self) -> ModelDefinition:
        profile = BUILTIN_PROVIDER_PROFILES.get(self.provider)
        if profile is None:
            raise ModelConfigurationError(
                f"unknown provider {self.provider!r}; known: {sorted(BUILTIN_PROVIDER_PROFILES)}"
            )
        if self.protocol != profile.protocol:
            raise ModelConfigurationError(
                f"provider {self.provider!r} speaks {profile.protocol!r}, not {self.protocol!r}"
            )
        if self.credential_ref not in ALLOWED_CREDENTIAL_REFS:
            raise ModelConfigurationError(
                f"credential_ref {self.credential_ref!r} is not a known secret field"
            )
        if self.credential_ref != profile.credential_ref:
            raise ModelConfigurationError(
                f"provider {self.provider!r} requires credential_ref "
                f"{profile.credential_ref!r}, not {self.credential_ref!r}"
            )
        validate_endpoint(self.resolved_endpoint, allow_http=self.allow_insecure_http)
        unknown_opts = set(self.provider_options) - set(profile.allowed_provider_options)
        if unknown_opts:
            raise ModelConfigurationError(
                f"provider options {sorted(unknown_opts)} are not allowlisted for "
                f"provider {self.provider!r}"
            )
        _validate_json_options(self.provider_options)
        if (
            self.reasoning.mode is ReasoningMode.ENABLED
            and Capability.REASONING not in self.capabilities
        ):
            raise ModelConfigurationError("enabled reasoning requires the 'reasoning' capability")
        if (
            self.reasoning.mode is not ReasoningMode.PROVIDER_DEFAULT
            and self.provider != "openrouter"
        ):
            raise ModelConfigurationError(
                f"provider {self.provider!r} has no verified non-default reasoning translation"
            )
        if Capability.TEXT not in self.capabilities:
            raise ModelConfigurationError("a model definition must declare the 'text' capability")
        object.__setattr__(self, "provider_options", deep_freeze(self.provider_options))
        return self

    @property
    def profile(self) -> ProviderProfile:
        return BUILTIN_PROVIDER_PROFILES[self.provider]

    @property
    def resolved_endpoint(self) -> str:
        """The explicit endpoint if set, else the provider's pinned URL."""
        return self.endpoint or BUILTIN_PROVIDER_PROFILES[self.provider].base_url

    def identity(self) -> SafeModelIdentity:
        """The credential-free, behavior-affecting identity of this definition."""
        return SafeModelIdentity(
            provider=self.provider,
            protocol=self.protocol,
            model_name=self.model_name,
            endpoint=self.resolved_endpoint,
            credential_ref=self.credential_ref,
            timeout_s=self.timeout_s,
            allow_insecure_http=self.allow_insecure_http,
            reasoning=tuple(
                sorted((k, canonical_json_value(v)) for k, v in self.reasoning.supplied().items())
            ),
            parameters=tuple(
                sorted((k, canonical_json_value(v)) for k, v in self.parameters.supplied().items())
            ),
            provider_options=tuple(
                sorted((k, canonical_json_value(v)) for k, v in self.provider_options.items())
            ),
            capabilities=tuple(sorted(c.value for c in self.capabilities)),
            pricing=(
                tuple(
                    sorted(
                        (key, canonical_json_value(value))
                        for key, value in self.pricing.model_dump(mode="json").items()
                    )
                )
                if self.pricing
                else None
            ),
            adapter_version=self.adapter_version,
            tool_schema_version=self.tool_schema_version,
        )

    def fingerprint(self) -> str:
        """A stable hex digest over every safe behavior-affecting setting."""
        return fingerprint(self.identity())

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def validate_invocation_options(self, options: Mapping[str, Any]) -> None:
        """Validate safe per-call options against this provider profile."""
        unknown = set(options) - _SAFE_INVOCATION_OPTIONS
        if unknown:
            raise ModelConfigurationError(
                f"per-call options {sorted(unknown)} are not allowlisted for "
                f"provider {self.provider!r}"
            )
        _validate_request_option_values(options)


def _validate_request_option_values(options: Mapping[str, Any]) -> None:
    for key, value in options.items():
        if key in {"temperature", "top_p"}:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ModelConfigurationError(f"{key} must be a finite number")
            if not math.isfinite(value):
                raise ModelConfigurationError(f"{key} must be a finite number")
        elif key in {"max_tokens", "seed"}:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ModelConfigurationError(f"{key} must be an integer")
            if key == "max_tokens" and value <= 0:
                raise ModelConfigurationError("max_tokens must be positive")
        elif key == "stop" and not isinstance(value, str):
            raise ModelConfigurationError("stop must be a string")


def _validate_json_options(options: Mapping[str, Any]) -> None:
    for key, value in options.items():
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ModelConfigurationError(
                f"provider option {key!r} must be JSON-compatible"
            ) from exc
