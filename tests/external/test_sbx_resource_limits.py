"""Black-box resource limit tests against the real ``sbx`` backend
(Phase 1A.1, Step 10).

Excluded from the default run - enable with::

    uv run pytest -m sbx

CPU and memory limits are already wired to ``sbx create --cpus``/``--memory``
(``SbxCli.build_create_argv``, Steps 2/4); the unit-level argv-building tests
already confirm the flags are constructed correctly. This module proves the
values are actually *applied* by the real sandbox, through the real
``SbxSandboxRuntime`` - not the raw CLI (already checked manually in the
Step 1 spike; see ``docs/findings/sbx-cli.md`` for the 1 GiB memory minimum
this backend enforces). Deliberately no OOM-killer test (the plan calls
those brittle).
"""

from __future__ import annotations

import pytest

from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime
from agentscope.runtime.workspace import WorkspaceRoot

pytestmark = [pytest.mark.external, pytest.mark.sbx]


@pytest.fixture
def workspace(tmp_path_factory: pytest.TempPathFactory) -> WorkspaceRoot:
    return WorkspaceRoot(path=tmp_path_factory.mktemp("sbx-resource-limits-workspace"))


def test_cpu_limit_is_applied(workspace: WorkspaceRoot) -> None:
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(cpu_limit=1), workspace)
    try:
        result = runtime.execute(ExecRequest(command=("nproc",)))
        assert result.exit_code == 0
        assert result.stdout.decode().strip() == "1"
    finally:
        runtime.close()


def test_memory_limit_is_applied(workspace: WorkspaceRoot) -> None:
    # 1 GiB is the sbx-enforced minimum (docs/findings/sbx-cli.md); confirm
    # the real sandbox reports a MemTotal consistent with that request.
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(memory_limit="1g"), workspace)
    try:
        result = runtime.execute(ExecRequest(command=("sh", "-c", "grep MemTotal /proc/meminfo")))
        assert result.exit_code == 0
        mem_total_kb = int(result.stdout.decode().split()[1])
        # Allow generous slack for kernel/reserved memory overhead.
        assert 900_000 <= mem_total_kb <= 1_100_000
    finally:
        runtime.close()
