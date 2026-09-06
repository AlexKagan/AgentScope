"""Unit tests: SbxSandboxRuntime rejects unsafe paths before invoking ``sbx``
(Phase 1A.1, Step 8).

AgentScope's own path confinement - not the real sandbox's mount boundary -
is the thing that must stop an unsafe path. This module proves rejection
happens before any external process is invoked, using a scripted CLI double
so no real ``sbx`` is needed:

- Absolute ``cwd`` and ``..`` traversal are already rejected at
  ``ExecRequest`` *construction* (Phase 0, see ``test_exec_types.py``) - such
  a request can never even be built, let alone reach ``execute()``.
- Symlink escape needs real filesystem resolution (``resolve_within``), which
  only runs inside ``SbxSandboxRuntime.execute()`` - this module exercises
  that path directly and asserts zero ``sbx exec`` calls occur.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

import pytest

from agentscope.runtime._sbx_cli import SbxCli
from agentscope.runtime.errors import PathEscapeError, RuntimeContractError
from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime
from agentscope.runtime.workspace import WorkspaceRoot


class _AlwaysSucceedsRunner:
    """A fake sbx runner that succeeds for any subcommand and records calls."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(
        self, argv: Sequence[str], *, timeout: float | None
    ) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(list(argv))
        return subprocess.CompletedProcess(args=(), returncode=0, stdout=b"ok\n", stderr=b"")

    def calls_for(self, subcommand: str) -> list[list[str]]:
        return [c for c in self.calls if c[1] == subcommand]


@pytest.fixture
def real_workspace(tmp_path: object) -> WorkspaceRoot:
    from pathlib import Path

    ws = Path(str(tmp_path)) / "ws"
    ws.mkdir()
    return WorkspaceRoot(path=ws)


def test_absolute_cwd_is_rejected_before_a_request_can_even_be_built() -> None:
    # Never reaches SbxSandboxRuntime at all: ExecRequest refuses to construct.
    with pytest.raises(RuntimeContractError):
        ExecRequest(command=("echo", "hi"), cwd="/etc")


def test_parent_traversal_cwd_is_rejected_before_a_request_can_even_be_built() -> None:
    with pytest.raises(RuntimeContractError):
        ExecRequest(command=("echo", "hi"), cwd="../escape")


def test_real_runtime_rejects_symlink_escape_before_invoking_sbx(
    tmp_path: object, real_workspace: WorkspaceRoot
) -> None:
    from pathlib import Path

    outside = Path(str(tmp_path)) / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")

    escape_link = real_workspace.path / "escape_link"
    escape_link.symlink_to(outside)

    runner = _AlwaysSucceedsRunner()
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), real_workspace, cli=SbxCli(runner=runner))

    # "escape_link" is a plain relative name - no ".." - so it passes
    # ExecRequest's syntactic check; only resolve_within's real filesystem
    # resolution catches that it escapes the workspace via a symlink.
    request = ExecRequest(command=("cat", "secret.txt"), cwd="escape_link")
    with pytest.raises(PathEscapeError):
        runtime.execute(request)

    assert runner.calls_for("exec") == []


def test_symlinked_command_argument_is_not_checked_by_resolve_within(
    tmp_path: object, real_workspace: WorkspaceRoot
) -> None:
    """Documents current scope, not a security claim: ``resolve_within`` only
    validates ``cwd``. A symlink named as a *command argument* (e.g. ``cat
    some_link``) is forwarded to ``sbx exec`` unexamined, same as any other
    argv value. Whether that symlink can actually be *followed* to read
    something outside the workspace is a real-backend question, answered
    empirically in ``tests/external/test_sbx_filesystem_isolation.py``
    (spoiler: no - the sandbox's own mount isolation means the symlink's
    target path does not exist inside the sandbox at all).
    """
    from pathlib import Path

    outside = Path(str(tmp_path)) / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")

    link_in_workspace = real_workspace.path / "link_to_secret.txt"
    link_in_workspace.symlink_to(outside / "secret.txt")

    runner = _AlwaysSucceedsRunner()
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), real_workspace, cli=SbxCli(runner=runner))

    # No PathEscapeError: only `cwd` goes through resolve_within, so this
    # request is accepted and forwarded - the fake CLI never actually reads
    # the file, so this only proves our code takes the "forward it" path.
    result = runtime.execute(ExecRequest(command=("cat", "link_to_secret.txt")))
    assert result.exit_code == 0
    assert len(runner.calls_for("exec")) == 1
