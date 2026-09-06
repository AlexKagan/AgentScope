"""Black-box filesystem isolation tests against the real ``sbx`` backend
(Phase 1A.1, Step 7).

Excluded from the default run - enable with::

    uv run pytest -m sbx

Phase 0 already proves path-policy *syntax* (``resolve_within`` rejects
absolute paths, ``..``, symlink escapes - see ``test_workspace_path.py``).
This module proves the actual sandbox mount boundary: that ``sbx`` itself
cannot see anything outside the one directory AgentScope hands it, using a
fixture deliberately outside the AgentScope repository (never the repo
itself, to avoid ever accidentally proving isolation against a directory
whose contents we don't fully control).
"""

from __future__ import annotations

import pytest

from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime
from agentscope.runtime.workspace import WorkspaceRoot

pytestmark = [pytest.mark.external, pytest.mark.sbx]


@pytest.fixture(scope="module")
def fixture_root(tmp_path_factory: pytest.TempPathFactory):
    root = tmp_path_factory.mktemp("sbx-fs-isolation")

    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "allowed.txt").write_text("allowed-content")

    outside = root / "outside"
    outside.mkdir()
    (outside / "host-secret.txt").write_text("host-secret-content")
    (outside / ".env").write_text("HOST_ENV_SECRET=leaked-if-visible")

    source_sentinel = root / "source-sentinel"
    source_sentinel.mkdir()
    (source_sentinel / "agentscope-secret-source.txt").write_text("source-sentinel-content")

    return root


@pytest.fixture(scope="module")
def workspace(fixture_root) -> WorkspaceRoot:
    return WorkspaceRoot(path=fixture_root / "workspace")


@pytest.fixture(scope="module")
def runtime(workspace: WorkspaceRoot) -> SbxSandboxRuntime:
    rt = SbxSandboxRuntime(SbxRuntimeConfig(), workspace)
    yield rt
    rt.close()


def test_workspace_file_is_readable(runtime: SbxSandboxRuntime) -> None:
    result = runtime.execute(ExecRequest(command=("cat", "allowed.txt")))
    assert result.exit_code == 0
    assert result.stdout == b"allowed-content"


def test_workspace_is_writable(runtime: SbxSandboxRuntime, workspace: WorkspaceRoot) -> None:
    result = runtime.execute(
        ExecRequest(command=("sh", "-c", "echo written-from-sandbox > new.txt"))
    )
    assert result.exit_code == 0
    assert (workspace.path / "new.txt").read_text() == "written-from-sandbox\n"


def test_sibling_outside_directory_is_unavailable(runtime: SbxSandboxRuntime, fixture_root) -> None:
    outside_path = fixture_root / "outside" / "host-secret.txt"
    result = runtime.execute(ExecRequest(command=("cat", str(outside_path))))
    assert result.exit_code != 0
    assert b"host-secret-content" not in result.stdout


def test_dotenv_outside_workspace_is_unavailable(runtime: SbxSandboxRuntime, fixture_root) -> None:
    dotenv_path = fixture_root / "outside" / ".env"
    result = runtime.execute(ExecRequest(command=("cat", str(dotenv_path))))
    assert result.exit_code != 0
    assert b"leaked-if-visible" not in result.stdout


def test_source_sentinel_is_unavailable(runtime: SbxSandboxRuntime, fixture_root) -> None:
    sentinel_path = fixture_root / "source-sentinel" / "agentscope-secret-source.txt"
    result = runtime.execute(ExecRequest(command=("cat", str(sentinel_path))))
    assert result.exit_code != 0
    assert b"source-sentinel-content" not in result.stdout


def test_relative_traversal_to_sibling_directory_fails(runtime: SbxSandboxRuntime) -> None:
    # Even if `sbx exec` were asked to `cat ../outside/host-secret.txt`
    # relative to the mounted workspace, there is nothing there to find:
    # only the workspace directory itself is bind-mounted into the sandbox.
    result = runtime.execute(
        ExecRequest(command=("sh", "-c", "cat ../outside/host-secret.txt 2>&1"))
    )
    assert result.exit_code != 0
    assert b"host-secret-content" not in result.stdout


def test_parent_directory_listing_does_not_reveal_siblings(runtime: SbxSandboxRuntime) -> None:
    result = runtime.execute(ExecRequest(command=("ls", "..")))
    assert b"outside" not in result.stdout
    assert b"source-sentinel" not in result.stdout


def test_symlink_inside_workspace_cannot_reach_outside_file(
    runtime: SbxSandboxRuntime, workspace: WorkspaceRoot, fixture_root
) -> None:
    # Phase 1A.1 Step 8: resolve_within only validates `cwd`, not command
    # arguments (see tests/unit/test_sbx_path_confinement.py) - so a symlink
    # named as an argument is forwarded to `sbx exec` unexamined. This proves
    # the real backend's own mount isolation is still a safety net: the
    # symlink's target (a host path outside the one mounted directory) does
    # not exist inside the sandbox at all, so following it fails regardless.
    link = workspace.path / "link_to_secret.txt"
    link.symlink_to(fixture_root / "outside" / "host-secret.txt")

    result = runtime.execute(ExecRequest(command=("cat", "link_to_secret.txt")))
    assert result.exit_code != 0
    assert b"host-secret-content" not in result.stdout
