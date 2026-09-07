"""Errors raised by runtime boundary policies and the runtime contract."""

from __future__ import annotations

__all__ = [
    "DisallowedEnvVarError",
    "HostEnvLookupError",
    "PathEscapeError",
    "RuntimeContractError",
    "SandboxBackendError",
    "SandboxCleanupError",
    "SandboxClosedError",
    "SandboxCreationError",
]


class RuntimeContractError(ValueError):
    """Raised when an ``ExecRequest`` / ``ExecResult`` violates the contract."""


class PathEscapeError(RuntimeContractError):
    """Raised when a model-facing path leaves the task workspace."""


class DisallowedEnvVarError(RuntimeContractError):
    """Raised (strict mode) when a non-allowlisted env var is requested."""


class HostEnvLookupError(RuntimeContractError):
    """Raised whenever code tries to read a host environment variable by name."""


class SandboxBackendError(RuntimeError):
    """Base for sbx-backend infrastructure failures with no ``ExecResult`` to
    carry them (unlike a command's own outcome, which is always an
    ``ExecResult`` - see ``ExecStatus.INFRA_FAILURE`` for that case)."""


class SandboxCreationError(SandboxBackendError):
    """Raised when the backend sandbox itself could not be created."""


class SandboxClosedError(SandboxBackendError):
    """Raised by any operation attempted on an already-``close()``d runtime."""


class SandboxCleanupError(SandboxBackendError):
    """Raised when a sandbox cannot be deterministically removed.

    The owning runtime remains retryable: callers may invoke ``close()`` again
    after the underlying infrastructure recovers.
    """
