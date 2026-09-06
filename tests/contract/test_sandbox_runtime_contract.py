"""Contract tests: a fake satisfies the SandboxRuntime contract (design 13.3)."""

from __future__ import annotations

import pytest

from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecResult, ExecStatus
from agentscope.runtime.sandbox import SandboxRuntime
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
