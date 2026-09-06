"""Configuration for the ``sbx`` (Docker Sandboxes) backend (Phase 1A.1, Step 2).

Values are constrained by empirically observed ``sbx`` CLI behavior rather
than assumption - see ``docs/findings/sbx-cli.md`` for the spike that
produced the 1 GiB memory minimum and the sandbox-name rules enforced below.
This module declares configuration shape only; it does not invoke ``sbx``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from agentscope.runtime.errors import RuntimeContractError

__all__ = ["NetworkPolicy", "SbxRuntimeConfig"]

# sbx enforces a hard floor of 1 GiB regardless of the requested value.
_MIN_MEMORY_BYTES = 1024**3
_MEMORY_PATTERN = re.compile(r"^(?P<value>[0-9]+)(?P<unit>[mMgG])$")
_MEMORY_UNIT_MULTIPLIER = {"m": 1024**2, "g": 1024**3}

# Mirrors sbx's own `--name` validation: at least two characters, starting
# with a letter or number, containing only letters, numbers, hyphens, and
# periods; "default" is reserved by sbx.
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]+$")
_RESERVED_NAMES = frozenset({"default"})


class NetworkPolicy(StrEnum):
    """Network egress policy applied to a sandbox.

    Only ``DISABLED`` is supported in Phase 1A.1: package-registry access and
    dynamic allowlists are explicitly out of scope (see the Phase 1A.1 plan).
    """

    DISABLED = "disabled"


def _parse_memory_bytes(memory_limit: str) -> int:
    match = _MEMORY_PATTERN.match(memory_limit)
    if not match:
        raise RuntimeContractError(
            f"memory_limit must look like '<positive integer><m|g>', got {memory_limit!r}"
        )
    value = int(match.group("value"))
    if value <= 0:
        raise RuntimeContractError(f"memory_limit must be positive, got {memory_limit!r}")
    return value * _MEMORY_UNIT_MULTIPLIER[match.group("unit").lower()]


@dataclass(frozen=True, slots=True)
class SbxRuntimeConfig:
    """Typed, validated configuration for :class:`SbxSandboxRuntime`.

    Exposes only the ``sbx`` options AgentScope actually needs - not every
    flag the CLI supports. Carries no secret material: this config is safe to
    log, serialize, or include in telemetry attributes.
    """

    template: str | None = None
    cpu_limit: int = 1
    memory_limit: str = "1g"
    sandbox_name_prefix: str = "agentscope"
    network_policy: NetworkPolicy = NetworkPolicy.DISABLED
    create_timeout_s: float = 60.0
    default_command_timeout_s: float = 30.0
    cleanup_timeout_s: float = 30.0

    def __post_init__(self) -> None:
        if self.template is not None and not self.template.strip():
            raise RuntimeContractError("template must not be blank when provided")

        if self.cpu_limit <= 0:
            raise RuntimeContractError(f"cpu_limit must be > 0, got {self.cpu_limit!r}")

        memory_bytes = _parse_memory_bytes(self.memory_limit)
        if memory_bytes < _MIN_MEMORY_BYTES:
            raise RuntimeContractError(
                f"memory_limit must be >= 1 GiB (the sbx-enforced minimum), "
                f"got {self.memory_limit!r}"
            )

        if len(self.sandbox_name_prefix) < 2:
            raise RuntimeContractError(
                f"sandbox_name_prefix must be at least 2 characters, "
                f"got {self.sandbox_name_prefix!r}"
            )
        if not _NAME_PATTERN.match(self.sandbox_name_prefix):
            raise RuntimeContractError(
                "sandbox_name_prefix must start with a letter or number and contain "
                f"only letters, numbers, hyphens, and periods: {self.sandbox_name_prefix!r}"
            )
        if self.sandbox_name_prefix.lower() in _RESERVED_NAMES:
            raise RuntimeContractError(
                f"sandbox_name_prefix {self.sandbox_name_prefix!r} is reserved by sbx"
            )

        for field_name in ("create_timeout_s", "default_command_timeout_s", "cleanup_timeout_s"):
            if getattr(self, field_name) <= 0:
                raise RuntimeContractError(f"{field_name} must be > 0")
