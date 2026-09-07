"""The typed execution request handed to a ``SandboxRuntime`` (design 10)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from agentscope.runtime.errors import RuntimeContractError

__all__ = ["ExecRequest"]


@dataclass(frozen=True, slots=True)
class ExecRequest:
    """A fully specified, boundary-safe command execution request.

    ``cwd`` is workspace-relative; ``env`` contains requested variables and is
    validated against the concrete runtime's allowlist at execution time.
    ``timeout_s`` of ``None`` means "use the backend's own configured
    default" (e.g. ``SbxRuntimeConfig.default_command_timeout_s``) rather than
    a value hardcoded into this backend-independent type.
    """

    command: tuple[str, ...]
    cwd: str = "."
    env: Mapping[str, str] = field(default_factory=dict)
    timeout_s: float | None = None
    max_output_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        if isinstance(self.command, str) or not isinstance(self.command, Sequence):
            raise RuntimeContractError("command must be a sequence of strings")
        cmd = tuple(str(part) for part in self.command)
        if not cmd:
            raise RuntimeContractError("command must not be empty")
        object.__setattr__(self, "command", cmd)

        pure = PurePosixPath(self.cwd)
        if pure.is_absolute():
            raise RuntimeContractError(f"cwd must be workspace-relative: {self.cwd!r}")
        if any(part == ".." for part in pure.parts):
            raise RuntimeContractError(f"cwd must not contain '..': {self.cwd!r}")

        object.__setattr__(self, "env", {str(k): str(v) for k, v in self.env.items()})

        if self.timeout_s is not None and self.timeout_s <= 0:
            raise RuntimeContractError("timeout_s must be > 0")
        if self.max_output_bytes <= 0:
            raise RuntimeContractError("max_output_bytes must be > 0")
