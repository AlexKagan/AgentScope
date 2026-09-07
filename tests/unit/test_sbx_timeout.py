"""Unit tests: SbxSandboxRuntime timeout handling (Phase 1A.1, Step 9).

The Step 1 spike proved Case B: killing the local ``sbx exec`` process does
NOT stop the remote command - only ``sbx stop`` does (see
docs/findings/sbx-cli.md). So a command timeout must invalidate the whole
sandbox, not just report the one command as failed. This module proves that
policy against a scripted CLI double (no real ``sbx`` needed); the actual
proof that the remote process really stops is the real-backend test in
``tests/external/test_sbx_timeout.py``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

import pytest

from agentscope.runtime._sbx_cli import SbxCli
from agentscope.runtime.errors import SandboxClosedError
from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecStatus
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime


class _TimeoutOnExecRunner:
    """Fake runner: `create`/`stop`/`rm` succeed; `exec` always times out locally."""

    def __init__(self, *, stop_returncode: int = 0, rm_returncode: int = 0) -> None:
        self.calls: list[list[str]] = []
        self._stop_returncode = stop_returncode
        self._rm_returncode = rm_returncode
        self._sandbox_name = ""
        self._exists = False

    def __call__(
        self, argv: Sequence[str], *, timeout: float | None
    ) -> subprocess.CompletedProcess[bytes]:
        argv = list(argv)
        self.calls.append(argv)
        subcommand = argv[1]
        if subcommand == "create":
            self._sandbox_name = argv[argv.index("--name") + 1]
            self._exists = True
        if subcommand == "exec":
            raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout or 0)
        if subcommand == "stop":
            return subprocess.CompletedProcess(
                args=(), returncode=self._stop_returncode, stdout=b"", stderr=b"stop failed"
            )
        if subcommand == "rm":
            if self._rm_returncode == 0:
                self._exists = False
            return subprocess.CompletedProcess(
                args=(), returncode=self._rm_returncode, stdout=b"", stderr=b"remove failed"
            )
        if subcommand == "ls":
            stdout = (
                f'{{"sandboxes":[{{"name":"{self._sandbox_name}"}}]}}'.encode()
                if self._exists
                else b'{"sandboxes":[]}'
            )
            return subprocess.CompletedProcess(args=(), returncode=0, stdout=stdout, stderr=b"")
        return subprocess.CompletedProcess(args=(), returncode=0, stdout=b"", stderr=b"")

    def calls_for(self, subcommand: str) -> list[list[str]]:
        return [c for c in self.calls if c[1] == subcommand]


def _timing_out_runtime(fake_workspace: object) -> tuple[SbxSandboxRuntime, _TimeoutOnExecRunner]:
    runner = _TimeoutOnExecRunner()
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    return runtime, runner


def test_command_timeout_returns_timed_out(fake_workspace: object) -> None:
    runtime, _runner = _timing_out_runtime(fake_workspace)
    result = runtime.execute(ExecRequest(command=("sleep", "999"), timeout_s=0.01))
    assert result.status is ExecStatus.TIMED_OUT
    assert result.exit_code is None


def test_timeout_issues_sbx_stop_to_kill_the_remote_process(fake_workspace: object) -> None:
    # This is the fix for the Step 1 finding: killing the local sbx exec
    # process alone does not stop the remote command - sbx stop does.
    runtime, runner = _timing_out_runtime(fake_workspace)
    runtime.execute(ExecRequest(command=("sleep", "999"), timeout_s=0.01))
    assert len(runner.calls_for("stop")) == 1
    (stop_argv,) = runner.calls_for("stop")
    assert runtime.name in stop_argv


def test_runtime_state_after_timeout_matches_documented_policy(fake_workspace: object) -> None:
    # Case B (plan Step 9): a timeout invalidates the whole sandbox, not just
    # the one command - further execute() calls must fail deterministically.
    runtime, _runner = _timing_out_runtime(fake_workspace)
    runtime.execute(ExecRequest(command=("sleep", "999"), timeout_s=0.01))
    with pytest.raises(SandboxClosedError):
        runtime.execute(ExecRequest(command=("echo", "too late")))


def test_close_after_timeout_still_removes_the_sandbox(fake_workspace: object) -> None:
    # INVALID must not be confused with CLOSED: the sandbox still exists
    # (stopped, not removed) after a timeout, so close() must still do real
    # cleanup - and remain idempotent afterward.
    runtime, runner = _timing_out_runtime(fake_workspace)
    runtime.execute(ExecRequest(command=("sleep", "999"), timeout_s=0.01))
    runtime.close()
    runtime.close()
    assert len(runner.calls_for("rm")) == 1


def test_timeout_forces_removal_when_stop_fails(fake_workspace: object) -> None:
    runner = _TimeoutOnExecRunner(stop_returncode=1)
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    result = runtime.execute(ExecRequest(command=("sleep", "999"), timeout_s=0.01))
    assert result.status is ExecStatus.TIMED_OUT
    assert len(runner.calls_for("rm")) == 1
    with pytest.raises(SandboxClosedError):
        runtime.execute(ExecRequest(command=("true",)))


def test_timeout_is_infra_failure_when_termination_cannot_be_confirmed(
    fake_workspace: object,
) -> None:
    runner = _TimeoutOnExecRunner(stop_returncode=1, rm_returncode=1)
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    result = runtime.execute(ExecRequest(command=("sleep", "999"), timeout_s=0.01))
    assert result.status is ExecStatus.INFRA_FAILURE
    assert "termination could not be confirmed" in result.message
    assert len(runner.calls_for("rm")) == 1
