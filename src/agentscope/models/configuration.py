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

from collections.abc import Mapping
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentscope.models.cost import PriceCard
from agentscope.models.errors import ModelConfigurationError
from agentscope.models.identity import ProviderProfile, SafeModelIdentity, fingerprint

__all__ = [
    "ALLOWED_CREDENTIAL_REFS",
    "BUILTIN_PROVIDER_PROFILES",
    "Capability",
    "ModelDefinition",
    "validate_endpoint",
]

# Symbolic SecretConfig fields a model definition may reference. Kept in sync
# with agentscope.config.secret.SecretConfig by a unit test.
ALLOWED_CREDENTIAL_REFS = frozenset({"openai_api_key", "openrouter_api_key", "meta_model_api_key"})

_SAFE_REQUEST_OPTIONS = frozenset({"temperature", "top_p", "max_tokens", "seed", "stop"})

BUILTIN_PROVIDER_PROFILES: dict[str, ProviderProfile] = {
    "meta": ProviderProfile(
        provider="meta",
        protocol="openai-chat-completions",
        base_url="https://api.meta.ai/v1",
        credential_ref="meta_model_api_key",
        allowed_request_options=_SAFE_REQUEST_OPTIONS,
    ),
    "openrouter": ProviderProfile(
        provider="openrouter",
        protocol="openai-chat-completions",
        base_url="https://openrouter.ai/api/v1",
        credential_ref="openrouter_api_key",
        allowed_request_options=_SAFE_REQUEST_OPTIONS,
    ),
}


class Capability(StrEnum):
    """A behavior a model definition can declare it requires now."""

    TEXT = "text"
    TOOL_CALLING = "tool_calling"


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

    model_config = ConfigDict(frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    provider: str
    protocol: str = "openai-chat-completions"
    model_name: str = Field(min_length=1)
    base_url: str | None = None
    credential_ref: str
    timeout_s: float = Field(default=60.0, gt=0)
    capabilities: tuple[Capability, ...] = (Capability.TEXT, Capability.TOOL_CALLING)
    reasoning_options: Mapping[str, Any] = Field(default_factory=dict)
    request_options: Mapping[str, str | int | float | bool] = Field(default_factory=dict)
    pricing: PriceCard | None = None
    adapter_version: str = "1.0.0"
    tool_schema_version: str = "1.0.0"
    allow_insecure_http: bool = False

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
        validate_endpoint(self.resolved_base_url, allow_http=self.allow_insecure_http)
        unknown_opts = set(self.request_options) - set(profile.allowed_request_options)
        if unknown_opts:
            raise ModelConfigurationError(
                f"request options {sorted(unknown_opts)} are not allowlisted for "
                f"provider {self.provider!r}"
            )
        if Capability.TEXT not in self.capabilities:
            raise ModelConfigurationError("a model definition must declare the 'text' capability")
        return self

    @property
    def profile(self) -> ProviderProfile:
        return BUILTIN_PROVIDER_PROFILES[self.provider]

    @property
    def resolved_base_url(self) -> str:
        """The explicit ``base_url`` if set, else the provider's pinned URL."""
        return self.base_url or BUILTIN_PROVIDER_PROFILES[self.provider].base_url

    def identity(self) -> SafeModelIdentity:
        """The credential-free, behavior-affecting identity of this definition."""
        return SafeModelIdentity(
            provider=self.provider,
            protocol=self.protocol,
            model_name=self.model_name,
            endpoint=self.resolved_base_url,
            credential_ref=self.credential_ref,
            reasoning_options=tuple(sorted((k, str(v)) for k, v in self.reasoning_options.items())),
            request_options=tuple(sorted((k, str(v)) for k, v in self.request_options.items())),
            capabilities=tuple(sorted(c.value for c in self.capabilities)),
            pricing_identity=self.pricing.identity if self.pricing else None,
            pricing_version=self.pricing.version if self.pricing else None,
            adapter_version=self.adapter_version,
            tool_schema_version=self.tool_schema_version,
        )

    def fingerprint(self) -> str:
        """A stable hex digest over every safe behavior-affecting setting."""
        return fingerprint(self.identity())

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities
