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

# The Python major.minor version AgentScope's sandbox image is expected to
# run (design/DoD: "Python 3.14 remains the sandbox baseline"). This is the
# single place to update when that requirement changes - e.g. bumping to
# "3.15" - so the test below fails loudly on a mismatch instead of the
# sandbox image silently drifting out from under an untested assumption.
EXPECTED_SANDBOX_PYTHON_VERSION = "3.14"


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
    # duration_s must reflect a real elapsed sbx exec call, not the silent
    # 0.0 default every ExecResult used to carry regardless of outcome.
    assert result.duration_s > 0


def test_sandbox_python_version_matches_expected_baseline(runtime: SbxSandboxRuntime) -> None:
    result = runtime.execute(ExecRequest(command=("python3", "--version")))
    assert result.exit_code == 0

    reported = result.stdout.decode().strip().removeprefix("Python ")
    major_minor = ".".join(reported.split(".")[:2])
    assert major_minor == EXPECTED_SANDBOX_PYTHON_VERSION, (
        f"sandbox image reports Python {reported!r}, expected "
        f"{EXPECTED_SANDBOX_PYTHON_VERSION}.x - update "
        "EXPECTED_SANDBOX_PYTHON_VERSION here (and docs/findings/sbx-cli.md) "
        "after verifying the new version's behavior, or investigate an "
        "unexpected upstream sandbox image change."
    )


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
