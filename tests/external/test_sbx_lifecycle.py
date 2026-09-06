"""Black-box lifecycle tests against the real ``sbx`` backend (Phase 1A.1,
Step 15).

Excluded from the default run - enable with::

    uv run pytest -m sbx

Step 4's lifecycle tests (``tests/unit/test_sbx_sandbox_runtime.py``) only
ever used a scripted CLI double. This module proves the same guarantees
against the actual ``sbx`` binary, verified through an independent channel
(``sbx ls --json`` run directly, not through our own ``SbxCli``) so the check
doesn't just confirm our own code's self-reporting: a sandbox really exists
after creation, really persists (not recreated) across multiple ``execute()``
calls, and really disappears after ``close()``.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from agentscope.runtime.errors import SandboxClosedError
from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime
from agentscope.runtime.workspace import WorkspaceRoot

pytestmark = [pytest.mark.external, pytest.mark.sbx]


def _real_sandbox_names() -> set[str]:
    completed = subprocess.run(["sbx", "ls", "--json"], capture_output=True, timeout=15, check=True)
    data = json.loads(completed.stdout)
    return {sb["name"] for sb in data.get("sandboxes", [])}


@pytest.fixture
def workspace(tmp_path_factory: pytest.TempPathFactory) -> WorkspaceRoot:
    return WorkspaceRoot(path=tmp_path_factory.mktemp("sbx-lifecycle-workspace"))


def test_runtime_creates_exactly_one_real_sandbox(workspace: WorkspaceRoot) -> None:
    before = _real_sandbox_names()
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), workspace)
    try:
        after = _real_sandbox_names()
        assert after - before == {runtime.name}
    finally:
        runtime.close()


def test_multiple_execute_calls_reuse_the_same_real_sandbox(workspace: WorkspaceRoot) -> None:
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), workspace)
    try:
        before = _real_sandbox_names()
        runtime.execute(ExecRequest(command=("echo", "1")))
        runtime.execute(ExecRequest(command=("echo", "2")))
        after = _real_sandbox_names()
        # Neither command created (or left behind) a new sandbox.
        assert after == before
        assert runtime.name in after
    finally:
        runtime.close()


def test_close_removes_the_real_sandbox(workspace: WorkspaceRoot) -> None:
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), workspace)
    name = runtime.name
    assert name in _real_sandbox_names()
    runtime.close()
    assert name not in _real_sandbox_names()


def test_close_is_idempotent_against_the_real_backend(workspace: WorkspaceRoot) -> None:
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), workspace)
    runtime.close()
    runtime.close()  # must not raise
    assert runtime.name not in _real_sandbox_names()


def test_execute_after_close_fails_deterministically_against_the_real_backend(
    workspace: WorkspaceRoot,
) -> None:
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), workspace)
    runtime.close()
    with pytest.raises(SandboxClosedError):
        runtime.execute(ExecRequest(command=("echo", "too late")))
