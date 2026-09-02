"""Reusable fakes for the Phase 0 test suite (no external services)."""

from __future__ import annotations

from dataclasses import dataclass

from agentscope.architectures.identity import ArchitectureIdentity
from agentscope.config.models import ModelIdentifier
from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecResult, ExecStatus
from agentscope.runtime.workspace import WorkspaceRoot


@dataclass
class DummyArchitecture:
    """A minimal object satisfying the ``AgentArchitecture`` protocol."""

    key: str = "dummy_agent"
    version: str = "0.1.0"

    @property
    def identity(self) -> ArchitectureIdentity:
        return ArchitectureIdentity(self.key, self.version)

    def describe(self) -> str:
        return f"dummy architecture {self.key} v{self.version}"


class FakeSandboxRuntime:
    """A ``SandboxRuntime`` that returns a configurable result and self-checks."""

    def __init__(self, workspace: WorkspaceRoot, result: ExecResult | None = None) -> None:
        self._workspace = workspace
        self._result = result or ExecResult(status=ExecStatus.COMPLETED, exit_code=0, stdout=b"ok")
        self.last_request: ExecRequest | None = None

    @property
    def workspace(self) -> WorkspaceRoot:
        return self._workspace

    def execute(self, request: ExecRequest) -> ExecResult:
        assert all(isinstance(v, str) for v in request.env.values())
        assert not request.cwd.startswith("/")
        self.last_request = request
        return self._result


class FakeModelClient:
    """An opaque stand-in for an authenticated model client."""


class FakeModelClientFactory:
    """Records the ``(model, api_key)`` it was called with; returns a fake client."""

    def __init__(self) -> None:
        self.calls: list[tuple[ModelIdentifier, str]] = []
        self.client = FakeModelClient()

    def __call__(self, model: ModelIdentifier, api_key: str) -> object:
        self.calls.append((model, api_key))
        return self.client
