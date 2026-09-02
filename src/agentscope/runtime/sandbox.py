"""The backend-independent sandbox execution contract (design 10).

Phase 0 defines only this protocol. Docker Sandboxes implement it in Phase 1A;
Phase 0 contract tests use fakes and make no claim about real process
termination, resource limits, network isolation, or mount behavior.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecResult
from agentscope.runtime.workspace import WorkspaceRoot

__all__ = ["SandboxRuntime"]


@runtime_checkable
class SandboxRuntime(Protocol):
    """An execution boundary for model-facing operations.

    Implementations must not accept an implicit host environment or an
    unrestricted host path: ``request.env`` is already filtered and
    ``request.cwd`` is workspace-relative.
    """

    @property
    def workspace(self) -> WorkspaceRoot:
        """The single directory exposed to executed commands."""
        ...

    def execute(self, request: ExecRequest) -> ExecResult:
        """Run ``request`` inside the sandbox and return a typed result."""
        ...
