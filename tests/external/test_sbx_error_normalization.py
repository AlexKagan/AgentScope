"""Black-box error-normalization tests against the real ``sbx`` backend
(Phase 1A.1, Step 13).

Excluded from the default run - enable with::

    uv run pytest -m sbx

Most of Step 13's normalization is already covered elsewhere: nonzero exit
codes are normal ``ExecResult``s, not exceptions (Step 5); timeouts have
distinct semantics via ``ExecStatus.TIMED_OUT`` (Step 9); raw ``subprocess``/
``OSError`` never escapes ``SbxCli.run`` (Step 3); creation failures raise
``SandboxCreationError`` (Step 4). This module documents the one confirmed
gap in that story: a sandbox removed *externally* (not through this
runtime's own ``close()``) cannot currently be told apart from a real
command legitimately exiting with the same code.
"""

from __future__ import annotations

import subprocess

import pytest

from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecStatus
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime
from agentscope.runtime.workspace import WorkspaceRoot

pytestmark = [pytest.mark.external, pytest.mark.sbx]


@pytest.fixture
def workspace(tmp_path_factory: pytest.TempPathFactory) -> WorkspaceRoot:
    return WorkspaceRoot(path=tmp_path_factory.mktemp("sbx-error-normalization-workspace"))


def test_externally_removed_sandbox_is_a_documented_known_gap(workspace: WorkspaceRoot) -> None:
    """Documents current behavior, not a correctness guarantee.

    ``sbx exec`` returns the same exit code (1) whether the sandbox itself
    vanished or the user's command legitimately exited 1 - the only
    distinguishing signal is unstructured stderr text ("ERROR: no sandbox
    named ..."), which is not a documented, stable API to parse (see
    docs/findings/sbx-cli.md). Team decision: document rather than build
    fragile stderr pattern-matching. Today this surfaces as a normal
    ``ExecStatus.COMPLETED`` result, not ``ExecStatus.INFRA_FAILURE``.
    """
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), workspace)
    try:
        # Remove the sandbox out-of-band - bypassing this runtime's own
        # close(), simulating something outside AgentScope interfering with
        # a sandbox AgentScope still believes is READY.
        subprocess.run(
            ["sbx", "rm", "-f", runtime.name], capture_output=True, timeout=15, check=False
        )

        result = runtime.execute(ExecRequest(command=("echo", "hi")))
        assert result.status is ExecStatus.COMPLETED
        assert result.exit_code == 1
    finally:
        runtime.close()  # safe even though the real sandbox is already gone
