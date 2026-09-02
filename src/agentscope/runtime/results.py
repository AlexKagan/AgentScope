"""The typed result returned by a ``SandboxRuntime`` (design 10).

Results distinguish a clean exit (with status code) from a timeout, an output
truncation, and an infrastructure failure - so callers never have to guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agentscope.runtime.errors import RuntimeContractError

__all__ = ["ExecResult", "ExecStatus"]


class ExecStatus(StrEnum):
    """Outcome category for a sandbox execution."""

    COMPLETED = "completed"  # the process ran to completion; see exit_code
    TIMED_OUT = "timed_out"  # killed after exceeding the timeout
    INFRA_FAILURE = "infra_failure"  # the runtime itself failed to execute


@dataclass(frozen=True, slots=True)
class ExecResult:
    """A boundary-safe execution result."""

    status: ExecStatus
    exit_code: int | None = None
    stdout: bytes = b""
    stderr: bytes = b""
    truncated: bool = False
    duration_s: float = 0.0
    message: str = ""

    def __post_init__(self) -> None:
        if self.status is ExecStatus.COMPLETED and self.exit_code is None:
            raise RuntimeContractError("COMPLETED result must carry an exit_code")
        if self.status is not ExecStatus.COMPLETED and self.exit_code is not None:
            raise RuntimeContractError(f"{self.status} result must not carry an exit_code")
        if self.duration_s < 0:
            raise RuntimeContractError("duration_s must be >= 0")
