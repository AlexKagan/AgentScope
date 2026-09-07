"""Black-box timeout tests against the real ``sbx`` backend (Phase 1A.1, Step 9).

Excluded from the default run - enable with::

    uv run pytest -m sbx

Replicates the Step 1 spike's heartbeat methodology (see
``docs/findings/sbx-cli.md``) through the actual ``SbxSandboxRuntime.execute()``
path, to prove the fix for the finding it produced: killing the local ``sbx
exec`` process does not stop the remote command, so ``execute()`` now issues
``sbx stop`` when a command times out. This is the real proof; the unit tests
in ``tests/unit/test_sbx_timeout.py`` only prove the *policy shape* against a
scripted double.
"""

from __future__ import annotations

import json
import subprocess
import time

import pytest

from agentscope.runtime.errors import SandboxClosedError
from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecStatus
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime
from agentscope.runtime.workspace import WorkspaceRoot


def _real_sandbox_names() -> set[str]:
    completed = subprocess.run(["sbx", "ls", "--json"], capture_output=True, timeout=15, check=True)
    data = json.loads(completed.stdout)
    return {sb["name"] for sb in data.get("sandboxes", [])}


pytestmark = [pytest.mark.external, pytest.mark.sbx]


@pytest.fixture
def workspace(tmp_path_factory: pytest.TempPathFactory) -> WorkspaceRoot:
    return WorkspaceRoot(path=tmp_path_factory.mktemp("sbx-timeout-workspace"))


@pytest.fixture
def runtime(workspace: WorkspaceRoot) -> SbxSandboxRuntime:
    rt = SbxSandboxRuntime(SbxRuntimeConfig(), workspace)
    yield rt
    rt.close()


def test_timed_out_process_is_not_still_running(
    runtime: SbxSandboxRuntime, workspace: WorkspaceRoot
) -> None:
    heartbeat = workspace.path / "heartbeat.txt"

    result = runtime.execute(
        ExecRequest(
            command=("sh", "-c", "while true; do date +%s%N >> heartbeat.txt; sleep 0.2; done"),
            timeout_s=2.0,
        )
    )

    assert result.status is ExecStatus.TIMED_OUT

    # The invariant this whole step exists to prove: once AgentScope reports
    # timed_out, the remote process must genuinely no longer be running -
    # not just that the local sbx exec call gave up waiting on it.
    assert heartbeat.exists()
    lines_at_timeout = heartbeat.read_text().count("\n")
    time.sleep(3)
    lines_after_wait = heartbeat.read_text().count("\n")
    assert lines_after_wait == lines_at_timeout, (
        "heartbeat file kept growing after timeout was reported - "
        "the remote process was not actually stopped"
    )


def test_timeout_finishes_within_bounded_wall_time(
    runtime: SbxSandboxRuntime,
) -> None:
    started = time.monotonic()
    result = runtime.execute(ExecRequest(command=("sh", "-c", "sleep 999"), timeout_s=2.0))
    elapsed = time.monotonic() - started
    assert result.status is ExecStatus.TIMED_OUT
    # Generous bound: local timeout (2s) + sbx stop overhead, well under a
    # runaway wait for the full "sleep 999".
    assert elapsed < 30.0


def test_cpu_bound_process_is_stopped_within_bound(runtime: SbxSandboxRuntime) -> None:
    started = time.monotonic()
    result = runtime.execute(
        ExecRequest(command=("python3", "-c", "exec('while True: pass')"), timeout_s=2.0)
    )
    assert result.status is ExecStatus.TIMED_OUT
    assert time.monotonic() - started < 30.0


def test_spawned_child_process_stops_modifying_workspace(
    runtime: SbxSandboxRuntime, workspace: WorkspaceRoot
) -> None:
    heartbeat = workspace.path / "child-heartbeat.txt"
    result = runtime.execute(
        ExecRequest(
            command=(
                "sh",
                "-c",
                "(while true; do echo child >> child-heartbeat.txt; sleep 0.2; done) & wait",
            ),
            timeout_s=2.0,
        )
    )
    assert result.status is ExecStatus.TIMED_OUT
    assert heartbeat.exists()
    size_at_timeout = heartbeat.stat().st_size
    time.sleep(3)
    assert heartbeat.stat().st_size == size_at_timeout


def test_runtime_is_invalid_after_timeout_against_real_backend(
    runtime: SbxSandboxRuntime,
) -> None:
    timeout_result = runtime.execute(ExecRequest(command=("sh", "-c", "sleep 999"), timeout_s=2.0))
    assert timeout_result.status is ExecStatus.TIMED_OUT

    with pytest.raises(SandboxClosedError):
        runtime.execute(ExecRequest(command=("echo", "too late")))


def test_close_after_timeout_removes_the_real_sandbox(workspace: WorkspaceRoot) -> None:
    # INVALID (stopped by the timeout handler) is not CLOSED (removed) - this
    # proves close() still performs real cleanup from that state, verified
    # through an independent channel (sbx ls), not just our own bookkeeping.
    runtime = SbxSandboxRuntime(SbxRuntimeConfig(), workspace)
    name = runtime.name
    timeout_result = runtime.execute(ExecRequest(command=("sh", "-c", "sleep 999"), timeout_s=2.0))
    assert timeout_result.status is ExecStatus.TIMED_OUT
    assert name in _real_sandbox_names()  # stopped, but still exists

    runtime.close()
    assert name not in _real_sandbox_names()
