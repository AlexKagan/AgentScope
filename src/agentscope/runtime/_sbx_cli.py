"""Private ``sbx`` CLI boundary (Phase 1A.1, Step 3).

This is an internal implementation detail of the ``sbx`` backend, not a
public protocol. It owns exactly one responsibility: invoke the local ``sbx``
binary safely.

Every invocation is argv-based - never a shell string - so user-supplied
command arguments and environment values are never reparsed by a host shell.
See ``docs/findings/sbx-cli.md`` for the empirical basis of the argument
shapes used here (e.g. why environment variables are always emitted as
``-e NAME=value``, never a bare ``-e NAME``).
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

__all__ = ["SbxCli", "SbxCliResult"]


class _SubprocessRunner(Protocol):
    """Injectable seam so the CLI boundary is unit-testable without Docker."""

    def __call__(
        self, argv: Sequence[str], *, timeout: float | None
    ) -> subprocess.CompletedProcess[bytes]: ...


def _default_runner(
    argv: Sequence[str], *, timeout: float | None
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603 - argv is a list, never a shell string
        list(argv), capture_output=True, timeout=timeout, check=False
    )


@dataclass(frozen=True, slots=True)
class SbxCliResult:
    """The outcome of one local ``sbx`` invocation.

    ``returncode`` is ``None`` when the local invocation itself could not
    complete (timeout, or the ``sbx`` binary could not be run) - this is
    distinct from the sandboxed command's own exit code, which is always a
    real integer when ``returncode`` is set.
    """

    returncode: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool
    error: str | None = None


class SbxCli:
    """Thin, argv-only boundary between AgentScope and the local ``sbx`` binary."""

    def __init__(self, *, binary: str = "sbx", runner: _SubprocessRunner | None = None) -> None:
        self._binary = binary
        self._runner = runner or _default_runner

    def run(self, args: Sequence[str], *, timeout_s: float) -> SbxCliResult:
        """Run ``sbx <args...>`` and return a captured, typed result.

        Never raises on subprocess-level failure (missing binary, local
        timeout) - those are reported via ``SbxCliResult`` fields so callers
        never need to catch raw ``subprocess`` exceptions.
        """
        argv = [self._binary, *args]
        try:
            completed = self._runner(argv, timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            return SbxCliResult(
                returncode=None,
                stdout=exc.stdout if isinstance(exc.stdout, bytes) else b"",
                stderr=exc.stderr if isinstance(exc.stderr, bytes) else b"",
                timed_out=True,
            )
        except OSError as exc:
            return SbxCliResult(
                returncode=None,
                stdout=b"",
                stderr=b"",
                timed_out=False,
                error=str(exc),
            )
        return SbxCliResult(
            returncode=completed.returncode,
            stdout=completed.stdout or b"",
            stderr=completed.stderr or b"",
            timed_out=False,
        )

    @staticmethod
    def build_exec_argv(
        sandbox: str,
        command: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> list[str]:
        """Build the argv for ``sbx exec`` - never a bare ``-e NAME``.

        ``cwd`` and each environment value are passed as their own argv
        elements (never concatenated into one flag string), and ``command``
        is appended unmodified and in order.
        """
        argv: list[str] = ["exec"]
        if cwd is not None:
            argv.extend(["-w", cwd])
        for key, value in (env or {}).items():
            argv.extend(["-e", f"{key}={value}"])
        argv.append(sandbox)
        argv.extend(command)
        return argv

    @staticmethod
    def build_create_argv(
        name: str,
        workspace_path: str,
        *,
        cpu_limit: int,
        memory_limit: str,
        deny_network: bool = True,
    ) -> list[str]:
        """Build the argv for ``sbx create shell`` (see docs/findings/sbx-cli.md).

        Uses the ``shell`` agent, the one suited to generic command execution,
        with exactly one workspace mounted at its host path.

        ``deny_network=True`` (the default) adds a sandbox-scoped
        ``--deny-network "**"`` - confirmed empirically to block all egress
        the same way the global deny-all policy does - so isolation does not
        depend solely on whatever the host's global network policy happens to
        be (plan Step 11: "prefer a sandbox-scoped deny-all policy rather than
        relying only on global machine configuration").
        """
        argv = [
            "create",
            "shell",
            workspace_path,
            "--name",
            name,
            "--cpus",
            str(cpu_limit),
            "--memory",
            memory_limit,
        ]
        if deny_network:
            argv.extend(["--deny-network", "**"])
        return argv

    @staticmethod
    def build_stop_argv(name: str) -> list[str]:
        """Build the argv for ``sbx stop`` - halts without removing state."""
        return ["stop", name]

    @staticmethod
    def build_rm_argv(name: str) -> list[str]:
        """Build the argv for ``sbx rm -f`` - final, forced teardown."""
        return ["rm", "-f", name]

    @staticmethod
    def build_list_argv() -> list[str]:
        """Build the machine-readable sandbox inventory command."""
        return ["ls", "--json"]
