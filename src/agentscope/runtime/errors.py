"""Errors raised by runtime boundary policies and the runtime contract."""

from __future__ import annotations

__all__ = [
    "DisallowedEnvVarError",
    "HostEnvLookupError",
    "PathEscapeError",
    "RuntimeContractError",
]


class RuntimeContractError(ValueError):
    """Raised when an ``ExecRequest`` / ``ExecResult`` violates the contract."""


class PathEscapeError(RuntimeContractError):
    """Raised when a model-facing path leaves the task workspace."""


class DisallowedEnvVarError(RuntimeContractError):
    """Raised (strict mode) when a non-allowlisted env var is requested."""


class HostEnvLookupError(RuntimeContractError):
    """Raised whenever code tries to read a host environment variable by name."""
