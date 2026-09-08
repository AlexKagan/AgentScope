"""Reusable fakes for the Phase 0 test suite (no external services)."""

from __future__ import annotations

from dataclasses import dataclass

from agentscope.architectures.identity import ArchitectureIdentity
from agentscope.models.configuration import ModelDefinition
from agentscope.models.identity import SafeModelIdentity
from agentscope.models.requests import ModelRequest
from agentscope.models.responses import ModelResponse
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
        self.close_calls = 0

    @property
    def workspace(self) -> WorkspaceRoot:
        return self._workspace

    def execute(self, request: ExecRequest) -> ExecResult:
        assert all(isinstance(v, str) for v in request.env.values())
        assert not request.cwd.startswith("/")
        self.last_request = request
        return self._result

    def close(self) -> None:
        self.close_calls += 1


class FakeModelAdapter:
    """A ``ModelAdapter`` whose identity matches its definition; never does I/O."""

    def __init__(self, definition: ModelDefinition, response: ModelResponse | None = None) -> None:
        self._identity = definition.identity()
        self._response = response
        self.calls: list[ModelRequest] = []
        self.close_calls = 0

    @property
    def identity(self) -> SafeModelIdentity:
        return self._identity

    async def ainvoke(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        if self._response is None:
            raise NotImplementedError("FakeModelAdapter has no scripted response")
        return self._response

    async def aclose(self) -> None:
        self.close_calls += 1


class FakeModelAdapterFactory:
    """Records the ``(definition, api_key)`` it was called with; returns a fake adapter."""

    def __init__(self) -> None:
        self.calls: list[tuple[ModelDefinition, str]] = []
        self.adapters: list[FakeModelAdapter] = []

    def __call__(self, definition: ModelDefinition, api_key: str) -> FakeModelAdapter:
        self.calls.append((definition, api_key))
        adapter = FakeModelAdapter(definition)
        self.adapters.append(adapter)
        return adapter
