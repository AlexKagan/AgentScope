"""The backend-independent sandbox execution contract (design 10).

Phase 0 defines only this protocol. Docker Sandboxes implement it in Phase 1A;
Phase 0 contract tests use fakes and make no claim about real process
termination, resource limits, network isolation, or mount behavior.

Phase 1A.1 amends the protocol (ADR 0004) with ``close()``: a real sandbox is
an expensive, stateful resource that must be deterministically released, so
lifecycle ownership belongs on the shared contract rather than on backend-
specific code that callers holding only a ``SandboxRuntime`` couldn't reach.
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
    unrestricted host path: implementations validate ``request.env`` against
    their policy and require ``request.cwd`` to be workspace-relative.

    **Phase 1A.1 amendment (ADR 0004):** The protocol now requires ``close()``.
    Phase 0 originally defined only ``workspace`` and ``execute()``. The ``close()``
    method was added in Phase 1A.1 because a sandbox is a stateful external
    resource that must be deterministically released, and callers holding only
    a ``SandboxRuntime`` reference need a way to guarantee cleanup without
    type casts or introspection. All implementations must provide an idempotent
    ``close()`` — subsequent calls after the first successful close are safe
    and should be no-ops.
    """

    @property
    def workspace(self) -> WorkspaceRoot:
        """The single directory exposed to executed commands."""
        ...

    def execute(self, request: ExecRequest) -> ExecResult:
        """Run ``request`` inside the sandbox and return a typed result."""
        ...

    def close(self) -> None:
        """Release the sandbox. Idempotent: calling this more than once is safe.

        Phase 1A.1 addition (ADR 0004 amendment). Implementations may raise
        a subclass of ``SandboxBackendError`` if cleanup fails but remains
        retryable (e.g., ``SandboxCleanupError``). Subsequent calls to
        ``close()`` will retry cleanup; failures do not advance the runtime
        to a "closed" state until confirmed success (or caller gives up).
        """
        ...
