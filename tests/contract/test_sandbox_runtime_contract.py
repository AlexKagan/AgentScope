"""Contract tests: a fake satisfies the SandboxRuntime contract (design 13.3).

Phase 1A.1 Step 14 extends this file rather than forking it: the same
contract assertions run against both ``FakeSandboxRuntime`` and the real
``SbxSandboxRuntime`` via the ``any_runtime`` fixture below, per the plan's
own rule - "do not create separate semantics for fake and real runtimes."
Assertions that only make sense for the fake's own configurability (e.g.
injecting a canned ``ExecResult``) stay fake-only above; anything that is a
real, backend-independent guarantee moves to the shared section.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecResult, ExecStatus
from agentscope.runtime.sandbox import SandboxRuntime
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime
from agentscope.runtime.workspace import WorkspaceRoot
from tests._fakes import FakeSandboxRuntime


def test_fake_is_a_sandbox_runtime(fake_workspace: object) -> None:
    assert isinstance(FakeSandboxRuntime(fake_workspace), SandboxRuntime)  # type: ignore[arg-type]


def test_completed_execution_carries_exit_code(fake_workspace: object) -> None:
    rt = FakeSandboxRuntime(fake_workspace)  # type: ignore[arg-type]
    result = rt.execute(ExecRequest(command=("echo", "hi"), env={"LANG": "C"}))
    assert result.status is ExecStatus.COMPLETED
    assert result.exit_code == 0
    assert rt.last_request is not None
    assert rt.last_request.cwd == "."


@pytest.mark.parametrize(
    "result",
    [
        ExecResult(status=ExecStatus.TIMED_OUT, message="deadline exceeded"),
        ExecResult(status=ExecStatus.INFRA_FAILURE, message="backend unavailable"),
        ExecResult(status=ExecStatus.COMPLETED, exit_code=1, truncated=True),
    ],
)
def test_result_categories_are_representable(fake_workspace: object, result: ExecResult) -> None:
    rt = FakeSandboxRuntime(fake_workspace, result=result)  # type: ignore[arg-type]
    assert rt.execute(ExecRequest(command=("x",))) is result


def test_request_cannot_carry_absolute_cwd() -> None:
    # The contract makes an unsafe request unrepresentable at construction time.
    with pytest.raises(ValueError):
        ExecRequest(command=("x",), cwd="/etc")


def test_close_is_idempotent(fake_workspace: object) -> None:
    # Phase 1A.1 (ADR 0004 amendment): close() joined the shared contract
    # because a real sandbox is a resource callers must be able to release
    # through the SandboxRuntime type alone, not just the concrete backend.
    rt = FakeSandboxRuntime(fake_workspace)  # type: ignore[arg-type]
    rt.close()
    rt.close()
    assert rt.close_calls == 2


# --- Shared contract: exercised against both the fake and the real sbx
# backend (Phase 1A.1, Step 14). The "sbx" row is marked external + sbx and
# excluded from the default run, same as every other real-backend test.


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("sbx", id="sbx", marks=[pytest.mark.external, pytest.mark.sbx]),
    ]
)
def any_runtime(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[SandboxRuntime]:
    workspace = WorkspaceRoot(path=tmp_path_factory.mktemp(f"contract-{request.param}-ws"))
    runtime: SandboxRuntime
    if request.param == "fake":
        runtime = FakeSandboxRuntime(workspace)  # type: ignore[arg-type]
    else:
        runtime = SbxSandboxRuntime(SbxRuntimeConfig(), workspace)
    yield runtime
    runtime.close()


def test_any_runtime_satisfies_sandbox_runtime_protocol(any_runtime: SandboxRuntime) -> None:
    assert isinstance(any_runtime, SandboxRuntime)  # type: ignore[arg-type]


def test_any_runtime_exposes_its_workspace(any_runtime: SandboxRuntime) -> None:
    assert isinstance(any_runtime.workspace, WorkspaceRoot)


def test_any_runtime_executes_a_simple_command(any_runtime: SandboxRuntime) -> None:
    result = any_runtime.execute(ExecRequest(command=("echo", "contract-check")))
    assert result.status is ExecStatus.COMPLETED
    assert result.exit_code == 0


def test_any_runtime_close_is_idempotent(any_runtime: SandboxRuntime) -> None:
    any_runtime.close()
    any_runtime.close()  # must not raise, regardless of backend
