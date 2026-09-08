"""Black-box network isolation tests against the real ``sbx`` backend
(Phase 1A.1, Step 11).

Excluded from the default run - enable with::

    uv run pytest -m sbx

``NetworkPolicy.DISABLED`` (the ``SbxRuntimeConfig`` default) now adds a
sandbox-scoped ``--deny-network "**"`` at creation time - confirmed by hand
to block egress the same way the machine's own global deny-all policy does
(see ``docs/findings/sbx-cli.md``). This module proves that through the real
``SbxSandboxRuntime``, and that local command execution is unaffected.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator

import pytest

from agentscope.runtime.errors import DisallowedEnvVarError
from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecStatus
from agentscope.runtime.sbx import NetworkPolicy, SbxRuntimeConfig, SbxSandboxRuntime
from agentscope.runtime.workspace import WorkspaceRoot

pytestmark = [pytest.mark.external, pytest.mark.sbx]


@pytest.fixture
def workspace(tmp_path_factory: pytest.TempPathFactory) -> WorkspaceRoot:
    return WorkspaceRoot(path=tmp_path_factory.mktemp("sbx-network-workspace"))


@pytest.fixture
def runtime(workspace: WorkspaceRoot) -> Iterator[SbxSandboxRuntime]:
    rt = SbxSandboxRuntime(SbxRuntimeConfig(network_policy=NetworkPolicy.DISABLED), workspace)
    yield rt
    rt.close()


def test_network_disabled_is_applied_at_creation(runtime: SbxSandboxRuntime) -> None:
    result = runtime.execute(
        ExecRequest(
            command=(
                "sh",
                "-c",
                'curl -s -m 5 -o /dev/null -w "%{http_code}" https://example.com',
            )
        )
    )
    assert result.exit_code == 0  # curl itself ran fine; the request was blocked
    assert result.stdout.decode().strip() != "200"


def test_local_command_execution_still_works_with_network_disabled(
    runtime: SbxSandboxRuntime,
) -> None:
    result = runtime.execute(ExecRequest(command=("echo", "still-works")))
    assert result.exit_code == 0
    assert result.stdout == b"still-works\n"


def test_network_policy_cannot_be_overridden_by_command_env(
    runtime: SbxSandboxRuntime,
) -> None:
    # Egress is blocked by the sandbox's own creation-time policy, not by
    # anything in the process environment - so no combination of explicit
    # env values handed to execute() can lift it.
    with pytest.raises(DisallowedEnvVarError):
        runtime.execute(
            ExecRequest(
                command=(
                    "sh",
                    "-c",
                    'curl -s -m 5 -o /dev/null -w "%{http_code}" https://example.com',
                ),
                env={"HTTP_PROXY": "", "NO_PROXY": "", "https_proxy": ""},
            )
        )


def test_raw_tcp_bytes_do_not_reach_host_service(runtime: SbxSandboxRuntime) -> None:
    listener = socket.socket()
    listener.bind(("0.0.0.0", 0))  # noqa: S104 - deliberate host-reachability probe
    listener.listen(1)
    listener.settimeout(5)
    port = listener.getsockname()[1]
    accepted = threading.Event()

    def accept_once() -> None:
        try:
            connection, _address = listener.accept()
            connection.close()
            accepted.set()
        except TimeoutError:
            pass

    thread = threading.Thread(target=accept_once)
    thread.start()
    try:
        result = runtime.execute(
            ExecRequest(
                command=(
                    "python3",
                    "-c",
                    "import socket; "
                    f"s=socket.create_connection(('host.docker.internal', {port}), timeout=3); "
                    "s.sendall(b'agentscope-probe')",
                ),
                timeout_s=10,
            )
        )
    finally:
        thread.join(timeout=6)
        listener.close()

    # sbx's transparent deny proxy may accept connect() locally, so the
    # command's exit code is not the security boundary. The controlled host
    # listener must never observe the attempted raw TCP connection.
    assert result.status is ExecStatus.COMPLETED
    assert not accepted.is_set(), "sandbox connected to a service on the host"
