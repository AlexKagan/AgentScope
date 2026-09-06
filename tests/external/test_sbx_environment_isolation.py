"""Black-box environment isolation tests against the real ``sbx`` backend
(Phase 1A.1, Step 6).

Excluded from the default run - enable with::

    uv run pytest -m sbx

These prove, through the real ``SbxSandboxRuntime.execute()`` path (not the
raw CLI, and not just the in-process ``build_sandbox_environment`` unit
tests), that: the sandbox never inherits the AgentScope host process's
environment, and an explicitly allowlisted variable does reach the sandbox.

Deliberately does *not* exercise ``SANDBOX_BASE_ENV`` defaults (e.g. `HOME`):
see the "Known gap" note in ``docs/findings/sbx-cli.md`` and
``runtime/README.md`` - those literals assume a `/workspace` mount point that
does not exist in the real backend, and are not yet wired into
`SbxSandboxRuntime` by any caller.

``test_secret_named_variable_rejected`` and ``test_sbx_invocation_never_uses_
bare_env_name`` from the Phase 1A.1 plan's Step 6 list are pure in-process
policy checks already covered by ``tests/unit/test_environment_policy.py``
(`test_non_allowlisted_var_is_rejected_in_strict_mode`) and
``tests/unit/test_sbx_cli.py`` (`test_sbx_cli_never_emits_bare_env_name`) -
not duplicated here since they need no real sandbox.
"""

from __future__ import annotations

import pytest

from agentscope.runtime.environment import build_sandbox_environment
from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.sbx import SbxRuntimeConfig, SbxSandboxRuntime
from agentscope.runtime.workspace import WorkspaceRoot

pytestmark = [pytest.mark.external, pytest.mark.sbx]


@pytest.fixture(scope="module")
def workspace(tmp_path_factory: pytest.TempPathFactory) -> WorkspaceRoot:
    return WorkspaceRoot(path=tmp_path_factory.mktemp("sbx-env-workspace"))


@pytest.fixture(scope="module")
def runtime(workspace: WorkspaceRoot) -> SbxSandboxRuntime:
    rt = SbxSandboxRuntime(SbxRuntimeConfig(), workspace)
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
    # build_sandbox_environment drops anything not on the allowlist by default.
    env = build_sandbox_environment({"AGENTSCOPE_NOT_ALLOWED": "should-not-appear"})
    assert "AGENTSCOPE_NOT_ALLOWED" not in env
    assert _read_var(runtime, "AGENTSCOPE_NOT_ALLOWED", env=env) == "absent"


def test_explicit_allowlisted_env_present(runtime: SbxSandboxRuntime) -> None:
    env = build_sandbox_environment(
        {"AGENTSCOPE_SAFE_TEST": "value"},
        allowlist=frozenset({"AGENTSCOPE_SAFE_TEST"}),
    )
    assert _read_var(runtime, "AGENTSCOPE_SAFE_TEST", env=env) == "value"
