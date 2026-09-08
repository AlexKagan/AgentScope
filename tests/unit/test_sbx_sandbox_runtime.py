"""Unit tests for ``SbxSandboxRuntime`` lifecycle (Phase 1A.1, Step 4).

A scripted fake runner stands in for the local ``sbx`` binary, so these tests
never touch Docker Sandboxes - they prove lifecycle *shape* (create-once,
reuse, idempotent close, deterministic failure after close/on failed
creation), not real isolation. Real-backend behavior is exercised separately
in the black-box suite (Step 15).
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence

import pytest

from agentscope.runtime._sbx_cli import SbxCli
from agentscope.runtime.errors import (
    DisallowedEnvVarError,
    SandboxCleanupError,
    SandboxClosedError,
    SandboxCreationError,
)
from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecStatus
from agentscope.runtime.sandbox import SandboxRuntime
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime


class _ScriptedSbxRunner:
    """Routes fake `sbx` responses by subcommand; records every call and the
    ``timeout`` each was invoked with."""

    def __init__(
        self,
        *,
        create_returncode: int = 0,
        exec_delay_s: float = 0.0,
        rm_returncodes: list[int] | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self.timeouts: list[float | None] = []
        self._create_returncode = create_returncode
        self._exec_delay_s = exec_delay_s
        self._rm_returncodes = list(rm_returncodes or [0])
        self._sandbox_name = ""
        self._exists = False

    def __call__(
        self, argv: Sequence[str], *, timeout: float | None
    ) -> subprocess.CompletedProcess[bytes]:
        argv = list(argv)
        self.calls.append(argv)
        self.timeouts.append(timeout)
        subcommand = argv[1]  # argv[0] is always the "sbx" binary name
        if subcommand == "create":
            self._sandbox_name = argv[argv.index("--name") + 1]
            self._exists = True  # also models a partial allocation on failure
            stderr = b"" if self._create_returncode == 0 else b"boom: creation failed"
            return subprocess.CompletedProcess(
                args=(), returncode=self._create_returncode, stdout=b"", stderr=stderr
            )
        if subcommand == "exec":
            if self._exec_delay_s:
                time.sleep(self._exec_delay_s)
            return subprocess.CompletedProcess(args=(), returncode=0, stdout=b"ok\n", stderr=b"")
        if subcommand == "rm":
            returncode = self._rm_returncodes.pop(0) if self._rm_returncodes else 0
            if returncode == 0:
                self._exists = False
            stderr = b"remove failed" if returncode else b""
            return subprocess.CompletedProcess(
                args=(), returncode=returncode, stdout=b"", stderr=stderr
            )
        if subcommand == "stop":
            return subprocess.CompletedProcess(args=(), returncode=0, stdout=b"", stderr=b"")
        if subcommand == "ls":
            stdout = (
                f'{{"sandboxes":[{{"name":"{self._sandbox_name}"}}]}}'.encode()
                if self._exists
                else b'{"sandboxes":[]}'
            )
            return subprocess.CompletedProcess(args=(), returncode=0, stdout=stdout, stderr=b"")
        raise AssertionError(f"unexpected sbx subcommand: {subcommand!r}")

    def calls_for(self, subcommand: str) -> list[list[str]]:
        return [c for c in self.calls if c[1] == subcommand]

    def timeout_for(self, subcommand: str) -> float | None:
        (index,) = [i for i, c in enumerate(self.calls) if c[1] == subcommand]
        return self.timeouts[index]


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


def test_execute_rejects_environment_not_allowed_by_runtime(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    runtime = _runtime(fake_workspace, runner)
    with pytest.raises(DisallowedEnvVarError):
        runtime.execute(ExecRequest(command=("env",), env={"SECRET": "value"}))
    assert runner.calls_for("exec") == []


def test_execute_passes_only_runtime_allowlisted_environment(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    config = SbxRuntimeConfig(env_allowlist=frozenset({"SAFE"}))
    runtime = SbxSandboxRuntime(config, fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    runtime.execute(ExecRequest(command=("env",), env={"SAFE": "value"}))
    (argv,) = runner.calls_for("exec")
    assert "SAFE=value" in argv
    assert not any(part.startswith("HOME=") for part in argv)


def test_execute_records_duration(fake_workspace: object) -> None:
    # A deterministic, non-flaky proxy for "duration reflects real elapsed
    # time": the fake exec call sleeps a known amount, so duration_s must be
    # at least that much rather than the previous silent default of 0.0.
    runner = _ScriptedSbxRunner(exec_delay_s=0.05)
    runtime = _runtime(fake_workspace, runner)
    result = runtime.execute(ExecRequest(command=("echo", "hi")))
    assert result.duration_s >= 0.05


def test_execute_uses_config_default_timeout_when_request_omits_it(
    fake_workspace: object,
) -> None:
    runner = _ScriptedSbxRunner()
    config = SbxRuntimeConfig(default_command_timeout_s=17.5)
    runtime = SbxSandboxRuntime(config, fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    runtime.execute(ExecRequest(command=("echo", "hi")))  # timeout_s left as None
    assert runner.timeout_for("exec") == 17.5


def test_execute_request_timeout_overrides_config_default(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    config = SbxRuntimeConfig(default_command_timeout_s=17.5)
    runtime = SbxSandboxRuntime(config, fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    runtime.execute(ExecRequest(command=("echo", "hi"), timeout_s=3.0))
    assert runner.timeout_for("exec") == 3.0


def test_create_uses_configured_create_timeout(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    config = SbxRuntimeConfig(create_timeout_s=42.0)
    SbxSandboxRuntime(config, fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    assert runner.timeout_for("create") == 42.0


def test_close_uses_configured_cleanup_timeout(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    config = SbxRuntimeConfig(cleanup_timeout_s=13.0)
    runtime = SbxSandboxRuntime(config, fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    runtime.close()
    assert runner.timeout_for("rm") == 13.0


class _FixedOutputRunner:
    """Fake runner returning caller-supplied stdout/stderr for every `exec`."""

    def __init__(self, *, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self._stdout = stdout
        self._stderr = stderr

    def __call__(
        self, argv: Sequence[str], *, timeout: float | None
    ) -> subprocess.CompletedProcess[bytes]:
        subcommand = list(argv)[1]
        if subcommand == "create":
            return subprocess.CompletedProcess(args=(), returncode=0, stdout=b"", stderr=b"")
        if subcommand == "exec":
            return subprocess.CompletedProcess(
                args=(), returncode=0, stdout=self._stdout, stderr=self._stderr
            )
        return subprocess.CompletedProcess(args=(), returncode=0, stdout=b"", stderr=b"")


def test_oversized_stdout_is_truncated_to_max_output_bytes(fake_workspace: object) -> None:
    full_stdout = b"x" * 1000
    runner = _FixedOutputRunner(stdout=full_stdout)
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    result = runtime.execute(ExecRequest(command=("echo", "big"), max_output_bytes=100))
    assert result.truncated is True
    assert len(result.stdout) == 100
    assert result.stdout == full_stdout[:100]


def test_oversized_stderr_is_truncated_and_flagged(fake_workspace: object) -> None:
    full_stderr = b"e" * 1000
    runner = _FixedOutputRunner(stderr=full_stderr)
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    result = runtime.execute(ExecRequest(command=("echo", "big"), max_output_bytes=100))
    assert result.truncated is True
    assert len(result.stderr) == 100
    assert result.stderr == full_stderr[:100]
    # stdout was empty and well within the limit - only stderr triggered truncation.
    assert result.stdout == b""


def test_output_limit_is_independent_per_stream(fake_workspace: object) -> None:
    runner = _FixedOutputRunner(stdout=b"o" * 800, stderr=b"e" * 800)
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    result = runtime.execute(ExecRequest(command=("emit",), max_output_bytes=1000))
    assert result.stdout == b"o" * 800
    assert result.stderr == b"e" * 800
    assert result.truncated is False


def test_output_within_limit_is_not_truncated(fake_workspace: object) -> None:
    runner = _FixedOutputRunner(stdout=b"small", stderr=b"also small")
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]
    result = runtime.execute(ExecRequest(command=("echo", "small"), max_output_bytes=1000))
    assert result.truncated is False
    assert result.stdout == b"small"
    assert result.stderr == b"also small"


class _MissingBinaryOnExecRunner:
    """`create` succeeds; `exec` fails as if the local `sbx` binary vanished."""

    def __call__(
        self, argv: Sequence[str], *, timeout: float | None
    ) -> subprocess.CompletedProcess[bytes]:
        subcommand = list(argv)[1]
        if subcommand == "create":
            return subprocess.CompletedProcess(args=(), returncode=0, stdout=b"", stderr=b"")
        raise FileNotFoundError("sbx: command not found")


class _MissingBinaryAlwaysRunner:
    """Every call fails as if the local `sbx` binary were never installed."""

    def __call__(
        self, argv: Sequence[str], *, timeout: float | None
    ) -> subprocess.CompletedProcess[bytes]:
        raise FileNotFoundError("sbx: command not found")


def test_missing_sbx_binary_at_creation_raises_creation_error(fake_workspace: object) -> None:
    with pytest.raises(SandboxCreationError):
        SbxSandboxRuntime(
            SbxRuntimeConfig(),
            fake_workspace,  # type: ignore[arg-type]
            cli=SbxCli(runner=_MissingBinaryAlwaysRunner()),
        )


def test_missing_sbx_binary_at_execute_is_infra_failure_not_raised(fake_workspace: object) -> None:
    # Unlike creation (which has no ExecResult to carry the failure in), a
    # missing binary discovered during execute() is a normal, representable
    # INFRA_FAILURE outcome - not an exception (see ExecStatus's own docstring).
    runtime = SbxSandboxRuntime(
        SbxRuntimeConfig(),
        fake_workspace,  # type: ignore[arg-type]
        cli=SbxCli(runner=_MissingBinaryOnExecRunner()),
    )
    result = runtime.execute(ExecRequest(command=("echo", "hi")))
    assert result.status is ExecStatus.INFRA_FAILURE
    assert result.exit_code is None
    assert "sbx" in result.message.lower() or "not found" in result.message.lower()


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


def test_close_failure_is_normalized_and_retryable(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner(rm_returncodes=[1, 0])
    runtime = _runtime(fake_workspace, runner)
    with pytest.raises(SandboxCleanupError, match="remove failed"):
        runtime.close()
    with pytest.raises(SandboxClosedError):
        runtime.execute(ExecRequest(command=("echo", "must-not-resume")))
    runtime.close()
    assert len(runner.calls_for("rm")) == 2


def test_close_accepts_independently_confirmed_absence(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner(rm_returncodes=[1])
    runtime = _runtime(fake_workspace, runner)
    runner._exists = False
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
    # Creation failure compensates for a potentially partial remote creation.
    assert runner.calls_for("exec") == []
    assert len(runner.calls_for("rm")) == 1


def test_failed_creation_reports_unconfirmed_compensating_cleanup(
    fake_workspace: object,
) -> None:
    runner = _ScriptedSbxRunner(create_returncode=1, rm_returncodes=[1])
    with pytest.raises(SandboxCreationError, match="compensating removal was not confirmed"):
        SbxSandboxRuntime(SbxRuntimeConfig(), fake_workspace, cli=SbxCli(runner=runner))  # type: ignore[arg-type]


def test_workspace_property_exposes_configured_root(fake_workspace: object) -> None:
    runner = _ScriptedSbxRunner()
    runtime = _runtime(fake_workspace, runner)
    assert runtime.workspace is fake_workspace
