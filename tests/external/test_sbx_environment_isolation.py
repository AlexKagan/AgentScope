"""Black-box environment isolation tests against the real ``sbx`` backend
(Phase 1A.1, Step 6).

Excluded from the default run - enable with::

    uv run pytest -m sbx

These prove, through the real ``SbxSandboxRuntime.execute()`` path (not the
raw CLI, and not just the in-process ``build_sandbox_environment`` unit
tests), that: the sandbox never inherits the AgentScope host process's
environment, and an explicitly allowlisted variable does reach the sandbox.

The runtime itself owns strict allowlist enforcement. Its explicit base
environment intentionally leaves ``HOME`` to the shell image's valid native
default because the real backend has no fixed ``/workspace`` mount point.
"""

from __future__ import annotations

import pytest

from agentscope.runtime.errors import DisallowedEnvVarError
from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime
from agentscope.runtime.workspace import WorkspaceRoot

pytestmark = [pytest.mark.external, pytest.mark.sbx]


@pytest.fixture(scope="module")
def workspace(tmp_path_factory: pytest.TempPathFactory) -> WorkspaceRoot:
    return WorkspaceRoot(path=tmp_path_factory.mktemp("sbx-env-workspace"))


@pytest.fixture(scope="module")
def runtime(workspace: WorkspaceRoot) -> SbxSandboxRuntime:
    rt = SbxSandboxRuntime(
        SbxRuntimeConfig(
            env_allowlist=frozenset({"LANG", "LC_ALL", "LC_CTYPE", "TZ", "AGENTSCOPE_SAFE_TEST"})
        ),
        workspace,
    )
    yield rt
    rt.close()


def _read_var(runtime: SbxSandboxRuntime, name: str, *, env: dict[str, str] | None = None) -> str:
    result = runtime.execute(
        ExecRequest(command=("sh", "-c", f'echo "${{{name}:-absent}}"'), env=env or {})
    )
    assert result.exit_code == 0
    return result.stdout.decode().strip()


def test_host_environment_is_not_inherited(
    monkeypatch: pytest.MonkeyPatch, runtime: SbxSandboxRuntime
) -> None:
    # Set on the *AgentScope host process* running this test - never passed
    # through ExecRequest.env - and confirm it cannot be observed inside the
    # sandbox purely by virtue of existing on the host.
    monkeypatch.setenv("AGENTSCOPE_SECRET_SENTINEL", "super-secret-value")
    assert _read_var(runtime, "AGENTSCOPE_SECRET_SENTINEL") == "absent"


def test_non_allowlisted_env_missing_inside_sandbox(runtime: SbxSandboxRuntime) -> None:
    assert _read_var(runtime, "AGENTSCOPE_NOT_ALLOWED") == "absent"


def test_explicit_allowlisted_env_present(runtime: SbxSandboxRuntime) -> None:
    assert (
        _read_var(runtime, "AGENTSCOPE_SAFE_TEST", env={"AGENTSCOPE_SAFE_TEST": "value"}) == "value"
    )


def test_direct_non_allowlisted_environment_is_rejected(runtime: SbxSandboxRuntime) -> None:
    with pytest.raises(DisallowedEnvVarError):
        _read_var(runtime, "SECRET", env={"SECRET": "value"})
