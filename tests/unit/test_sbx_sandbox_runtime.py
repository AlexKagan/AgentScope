"""Unit tests for ``SbxSandboxRuntime`` lifecycle (Phase 1A.1, Step 4).

A scripted fake runner stands in for the local ``sbx`` binary, so these tests
never touch Docker Sandboxes - they prove lifecycle *shape* (create-once,
reuse, idempotent close, deterministic failure after close/on failed
creation), not real isolation. Real-backend behavior is exercised separately
in the black-box suite (Step 15).
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

import pytest

from agentscope.runtime._sbx_cli import SbxCli
from agentscope.runtime.errors import SandboxClosedError, SandboxCreationError
from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecStatus
from agentscope.runtime.sandbox import SandboxRuntime
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime


class _ScriptedSbxRunner:
    """Routes fake `sbx` responses by subcommand; records every call."""

    def __init__(self, *, create_returncode: int = 0) -> None:
        self.calls: list[list[str]] = []
        self._create_returncode = create_returncode

    def __call__(
        self, argv: Sequence[str], *, timeout: float | None
    ) -> subprocess.CompletedProcess[bytes]:
        argv = list(argv)
        self.calls.append(argv)
        subcommand = argv[1]  # argv[0] is always the "sbx" binary name
        if subcommand == "create":
            stderr = b"" if self._create_returncode == 0 else b"boom: creation failed"
            return subprocess.CompletedProcess(
                args=(), returncode=self._create_returncode, stdout=b"", stderr=stderr
            )
        if subcommand == "exec":
            return subprocess.CompletedProcess(args=(), returncode=0, stdout=b"ok\n", stderr=b"")
        if subcommand in ("stop", "rm"):
            return subprocess.CompletedProcess(args=(), returncode=0, stdout=b"", stderr=b"")
        raise AssertionError(f"unexpected sbx subcommand: {subcommand!r}")

    def calls_for(self, subcommand: str) -> list[list[str]]:
        return [c for c in self.calls if c[1] == subcommand]


def _runtime(fake_workspace: object, runner: _ScriptedSbxRunner) -> SbxSandboxRuntime:
    return SbxSandboxRuntime(SbxRuntimeConfig(), fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]


def test_runtime_satisfies_sandbox_runtime_protocol(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    runtime = _runtime(fake_workspace, runner)
    assert isinstance(runtime, SandboxRuntime)  # type: ignore[arg-type]


def test_runtime_creates_single_sandbox(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    _runtime(fake_workspace, runner)
    assert len(runner.calls_for("create")) == 1


def test_created_sandbox_name_is_collision_safe(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    first = _runtime(fake_workspace, runner)
    second = _runtime(fake_workspace, runner)
    assert first.name != second.name


def test_create_argv_uses_workspace_and_resource_limits(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    config = SbxRuntimeConfig(cpu_limit=3, memory_limit="4g")
    SbxSandboxRuntime(config, fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    (create_argv,) = runner.calls_for("create")
    assert str(fake_workspace.path) in create_argv  # type: ignore[attr-defined]
    assert create_argv[create_argv.index("--cpus") + 1] == "3"
    assert create_argv[create_argv.index("--memory") + 1] == "4g"


def test_multiple_execute_calls_reuse_same_sandbox(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    runtime = _runtime(fake_workspace, runner)
    runtime.execute(ExecRequest(command=("echo", "1")))
    runtime.execute(ExecRequest(command=("echo", "2")))
    assert len(runner.calls_for("create")) == 1
    assert len(runner.calls_for("exec")) == 2


def test_execute_returns_completed_result(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    runtime = _runtime(fake_workspace, runner)
    result = runtime.execute(ExecRequest(command=("echo", "hi")))
    assert result.status is ExecStatus.COMPLETED
    assert result.exit_code == 0


def test_close_removes_sandbox(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    runtime = _runtime(fake_workspace, runner)
    runtime.close()
    assert len(runner.calls_for("rm")) == 1


def test_close_is_idempotent(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    runtime = _runtime(fake_workspace, runner)
    runtime.close()
    runtime.close()
    runtime.close()
    assert len(runner.calls_for("rm")) == 1


def test_execute_after_close_fails_deterministically(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    runtime = _runtime(fake_workspace, runner)
    runtime.close()
    with pytest.raises(SandboxClosedError):
        runtime.execute(ExecRequest(command=("echo", "too late")))


def test_failed_creation_does_not_leave_runtime_ready(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner(create_returncode=1)
    with pytest.raises(SandboxCreationError):
        SbxSandboxRuntime(SbxRuntimeConfig(), fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    # Creation failure must never attempt to run a command or remove a
    # sandbox that was never successfully created.
    assert runner.calls_for("exec") == []
    assert runner.calls_for("rm") == []


def test_workspace_property_exposes_configured_root(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    runtime = _runtime(fake_workspace, runner)
    assert runtime.workspace is fake_workspace
