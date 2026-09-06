"""Unit tests for the private ``sbx`` CLI boundary (Phase 1A.1, Step 3).

These tests never invoke a real subprocess or require ``sbx`` to be
installed: a fake runner records exactly what argv it was called with, so we
can prove the boundary never builds a shell string and never reparses
arguments.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

import pytest

from agentscope.runtime._sbx_cli import SbxCli, SbxCliResult


class _RecordingRunner:
    """A fake subprocess runner that records every call it receives."""

    def __init__(self, completed: subprocess.CompletedProcess[bytes] | None = None) -> None:
        self.calls: list[tuple[Sequence[str], float | None]] = []
        self._completed = completed or subprocess.CompletedProcess(
            args=(), returncode=0, stdout=b"ok", stderr=b""
        )

    def __call__(
        self, argv: Sequence[str], *, timeout: float | None
    ) -> subprocess.CompletedProcess[bytes]:
        # A shell-based implementation would call this with a single string.
        assert not isinstance(argv, str)
        self.calls.append((list(argv), timeout))
        return self._completed


class _TimeoutRunner:
    def __call__(
        self, argv: Sequence[str], *, timeout: float | None
    ) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(cmd=list(argv), timeout=timeout or 0)


class _MissingBinaryRunner:
    def __call__(
        self, argv: Sequence[str], *, timeout: float | None
    ) -> subprocess.CompletedProcess[bytes]:
        raise FileNotFoundError("sbx: command not found")


def test_sbx_cli_uses_argv_not_shell() -> None:
    runner = _RecordingRunner()
    cli = SbxCli(runner=runner)
    cli.run(["ls"], timeout_s=5.0)
    ((argv, _timeout),) = runner.calls
    assert argv == ["sbx", "ls"]
    assert all(isinstance(part, str) for part in argv)


def test_sbx_cli_passes_workspace_as_separate_argument() -> None:
    argv = SbxCli.build_exec_argv("my-sandbox", ("echo", "hi"), cwd="/task/workspace")
    # "-w" and its value must be two distinct argv elements, never "-w=..." or "-w /x".
    index = argv.index("-w")
    assert argv[index + 1] == "/task/workspace"
    assert argv[index + 1] != "-w=/task/workspace"


def test_sbx_cli_passes_environment_as_separate_arguments() -> None:
    argv = SbxCli.build_exec_argv("my-sandbox", ("env",), env={"LANG": "C", "TZ": "UTC"})
    assert argv.count("-e") == 2
    values = [argv[i + 1] for i, part in enumerate(argv) if part == "-e"]
    assert values == ["LANG=C", "TZ=UTC"]


def test_sbx_cli_never_emits_bare_env_name() -> None:
    # A bare "-e NAME" tells sbx to copy the value from the *local* process
    # environment - confirmed live-leak behavior (docs/findings/sbx-cli.md).
    argv = SbxCli.build_exec_argv("my-sandbox", ("env",), env={"SECRET_LOOKING_NAME": "x"})
    for i, part in enumerate(argv):
        if part == "-e":
            assert "=" in argv[i + 1]


def test_sbx_cli_preserves_command_arguments() -> None:
    command = ("python", "-c", "print(21 * 2)")
    argv = SbxCli.build_exec_argv("my-sandbox", command)
    assert argv[-3:] == list(command)


@pytest.mark.parametrize(
    "hostile_arg",
    ["; rm -rf /", "$(env)", "hello && something", "`whoami`", "a; b|c"],
)
def test_sbx_cli_does_not_interpolate_command_strings(hostile_arg: str) -> None:
    argv = SbxCli.build_exec_argv("my-sandbox", ("echo", hostile_arg))
    # The hostile string survives as exactly one argv element, untouched.
    assert argv[-1] == hostile_arg
    assert argv.count(hostile_arg) == 1


def test_sbx_cli_build_exec_argv_without_cwd_or_env() -> None:
    argv = SbxCli.build_exec_argv("my-sandbox", ("true",))
    assert argv == ["exec", "my-sandbox", "true"]


def test_sbx_cli_run_returns_captured_output() -> None:
    completed = subprocess.CompletedProcess(args=(), returncode=7, stdout=b"out", stderr=b"err")
    cli = SbxCli(runner=_RecordingRunner(completed))
    result = cli.run(["exec", "sandbox", "false"], timeout_s=5.0)
    assert result == SbxCliResult(
        returncode=7, stdout=b"out", stderr=b"err", timed_out=False, error=None
    )


def test_sbx_cli_passes_timeout_through_to_runner() -> None:
    runner = _RecordingRunner()
    cli = SbxCli(runner=runner)
    cli.run(["ls"], timeout_s=12.5)
    ((_argv, timeout),) = runner.calls
    assert timeout == 12.5


def test_sbx_cli_reports_timeout_without_raising() -> None:
    cli = SbxCli(runner=_TimeoutRunner())
    result = cli.run(["exec", "sandbox", "sleep", "999"], timeout_s=0.01)
    assert result.timed_out is True
    assert result.returncode is None


def test_sbx_cli_reports_missing_binary_without_raising() -> None:
    cli = SbxCli(runner=_MissingBinaryRunner())
    result = cli.run(["version"], timeout_s=5.0)
    assert result.timed_out is False
    assert result.returncode is None
    assert result.error is not None


def test_sbx_cli_default_binary_is_sbx() -> None:
    runner = _RecordingRunner()
    cli = SbxCli(runner=runner)
    cli.run(["version"], timeout_s=5.0)
    ((argv, _timeout),) = runner.calls
    assert argv[0] == "sbx"
