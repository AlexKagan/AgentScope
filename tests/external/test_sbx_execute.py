"""Component tests: ``SbxSandboxRuntime.execute()`` against the real ``sbx``
backend (Phase 1A.1, Step 5).

Excluded from the default run - enable with::

    uv run pytest -m sbx

Requires the `sbx` CLI installed and authenticated (`sbx login`), and a
global network policy already initialized (`sbx policy init ...`). See
``docs/findings/sbx-cli.md`` for the one-time setup and the empirical basis
for this module's assumptions (workspace mounted at its host path, no shell
reinterpretation of arguments, etc).

Step 4's unit tests already prove lifecycle *shape* against a scripted CLI
double; this module proves the actual command-execution semantics the plan's
Step 5 calls out, against the real sandbox.
"""

from __future__ import annotations

import pytest

from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecStatus
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime
from agentscope.runtime.workspace import WorkspaceRoot

pytestmark = [pytest.mark.external, pytest.mark.sbx]


@pytest.fixture(scope="module")
def workspace(tmp_path_factory: pytest.TempPathFactory) -> WorkspaceRoot:
    return WorkspaceRoot(path=tmp_path_factory.mktemp("sbx-execute-workspace"))


@pytest.fixture(scope="module")
def runtime(workspace: WorkspaceRoot) -> SbxSandboxRuntime:
    rt = SbxSandboxRuntime(SbxRuntimeConfig(), workspace)
    yield rt
    rt.close()


def test_execute_success(runtime: SbxSandboxRuntime) -> None:
    # The plan's final Step 5 acceptance scenario, run against the real backend.
    result = runtime.execute(ExecRequest(command=("python3", "-c", "print(21 * 2)")))
    assert result.status is ExecStatus.COMPLETED
    assert result.exit_code == 0
    assert result.stdout == b"42\n"
    assert result.stderr == b""


def test_execute_captures_stdout(runtime: SbxSandboxRuntime) -> None:
    result = runtime.execute(ExecRequest(command=("echo", "hello-stdout")))
    assert result.stdout == b"hello-stdout\n"


def test_execute_captures_stderr(runtime: SbxSandboxRuntime) -> None:
    result = runtime.execute(ExecRequest(command=("sh", "-c", "echo err-out >&2")))
    assert result.stderr == b"err-out\n"
    assert result.stdout == b""


def test_execute_preserves_nonzero_exit_code(runtime: SbxSandboxRuntime) -> None:
    result = runtime.execute(ExecRequest(command=("sh", "-c", "exit 7")))
    assert result.status is ExecStatus.COMPLETED
    assert result.exit_code == 7


@pytest.mark.parametrize("hostile_arg", ["; rm -rf /", "$(echo pwned)", "a && b", "`whoami`"])
def test_execute_preserves_argument_boundaries(
    runtime: SbxSandboxRuntime, hostile_arg: str
) -> None:
    result = runtime.execute(
        ExecRequest(command=("python3", "-c", "import sys; print(sys.argv[1])", hostile_arg))
    )
    assert result.exit_code == 0
    assert result.stdout.decode().strip() == hostile_arg


def test_execute_uses_requested_cwd(runtime: SbxSandboxRuntime, workspace: WorkspaceRoot) -> None:
    subdir = workspace.path / "cwd-subdir"
    subdir.mkdir(exist_ok=True)
    (subdir / "marker.txt").write_text("here")
    result = runtime.execute(ExecRequest(command=("cat", "marker.txt"), cwd="cwd-subdir"))
    assert result.exit_code == 0
    assert result.stdout == b"here"


def test_multiple_commands_share_workspace(
    runtime: SbxSandboxRuntime, workspace: WorkspaceRoot
) -> None:
    write_result = runtime.execute(ExecRequest(command=("sh", "-c", "echo shared > shared.txt")))
    assert write_result.exit_code == 0

    read_result = runtime.execute(ExecRequest(command=("cat", "shared.txt")))
    assert read_result.stdout == b"shared\n"

    # The write is visible directly on the host too - same mounted workspace.
    assert (workspace.path / "shared.txt").read_text() == "shared\n"
