"""Unit tests for ExecRequest / ExecResult contract types (design 10, 13.1)."""

from __future__ import annotations

import pytest

from agentscope.runtime.errors import RuntimeContractError
from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecResult, ExecStatus


def test_minimal_valid_request() -> None:
    req = ExecRequest(command=("echo", "hi"))
    assert req.command == ("echo", "hi")
    assert req.cwd == "."
    assert req.env == {}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"command": ()},
        {"command": "echo hi"},
        {"command": ("echo",), "cwd": "/abs"},
        {"command": ("echo",), "cwd": "../escape"},
        {"command": ("echo",), "timeout_s": 0},
        {"command": ("echo",), "max_output_bytes": 0},
    ],
)
def test_invalid_requests_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(RuntimeContractError):
        ExecRequest(**kwargs)  # type: ignore[arg-type]


def test_env_values_are_coerced_to_str() -> None:
    req = ExecRequest(command=("env",), env={"A": 1})  # type: ignore[dict-item]
    assert req.env == {"A": "1"}


def test_completed_result_requires_exit_code() -> None:
    with pytest.raises(RuntimeContractError):
        ExecResult(status=ExecStatus.COMPLETED)
    ok = ExecResult(status=ExecStatus.COMPLETED, exit_code=0)
    assert ok.exit_code == 0


@pytest.mark.parametrize("status", [ExecStatus.TIMED_OUT, ExecStatus.INFRA_FAILURE])
def test_non_completed_result_forbids_exit_code(status: ExecStatus) -> None:
    with pytest.raises(RuntimeContractError):
        ExecResult(status=status, exit_code=1)
    assert ExecResult(status=status).exit_code is None
