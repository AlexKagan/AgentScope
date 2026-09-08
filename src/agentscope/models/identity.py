"""Safe model identity and reproducibility fingerprint (design 7, D3).

These types capture everything about a model configuration that affects
behavior *and* is safe to persist: provider, protocol, model name, endpoint
identity, reasoning options, allowlisted request options, pricing identity and
version, adapter version, and tool-schema version. They never carry a
credential or a live client object.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

__all__ = ["ProviderProfile", "SafeModelIdentity", "fingerprint"]


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    """A built-in commercial/service boundary and its safe defaults.

    ``provider`` is the service identity (``meta``, ``openrouter``); it is not a
    URL. ``protocol`` selects request/response semantics and the adapter mode.
    ``allowed_request_options`` is the explicit per-profile allowlist of safe
    provider request kwargs — anything else is rejected during validation.
    """

    provider: str
    protocol: str
    base_url: str
    credential_ref: str
    allowed_request_options: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class SafeModelIdentity:
    """Behavior-affecting, credential-free identity of a model configuration."""

    provider: str
    protocol: str
    model_name: str
    endpoint: str
    credential_ref: str
    reasoning_options: tuple[tuple[str, str], ...]
    request_options: tuple[tuple[str, str], ...]
    capabilities: tuple[str, ...]
    pricing_identity: str | None
    pricing_version: str | None
    adapter_version: str
    tool_schema_version: str

    def canonical_dict(self) -> dict[str, object]:
        """A deterministically ordered mapping of the safe identity fields."""
        return {
            "provider": self.provider,
            "protocol": self.protocol,
            "model_name": self.model_name,
            "endpoint": self.endpoint,
            "credential_ref": self.credential_ref,
            "reasoning_options": [list(pair) for pair in self.reasoning_options],
            "request_options": [list(pair) for pair in self.request_options],
            "capabilities": list(self.capabilities),
            "pricing_identity": self.pricing_identity,
            "pricing_version": self.pricing_version,
            "adapter_version": self.adapter_version,
            "tool_schema_version": self.tool_schema_version,
        }


def fingerprint(identity: SafeModelIdentity) -> str:
    """Return a stable hex digest over every safe behavior-affecting setting.

    The digest changes when any behavior-affecting option changes and does not
    change when only the credential *value* is rotated (the identity holds only
    the symbolic ``credential_ref``, never the secret).
    """
    payload = json.dumps(identity.canonical_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
