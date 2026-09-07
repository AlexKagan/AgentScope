"""The ``sbx`` (Docker Sandboxes) backend (Phase 1A.1).

``SbxRuntimeConfig`` (Step 2) declares configuration shape, constrained by
empirically observed ``sbx`` CLI behavior rather than assumption - see
``docs/findings/sbx-cli.md`` for the spike that produced the 1 GiB memory
minimum and the sandbox-name rules enforced below.

``SbxSandboxRuntime`` (Step 4) implements the ``SandboxRuntime`` protocol by
driving one persistent sandbox through the ``_sbx_cli`` boundary: create at
construction, reuse for every ``execute()`` call, release on ``close()``.
Creation happens eagerly in ``__init__`` so a runtime object only ever exists
in a usable state - there is no separate "half-initialized" state to leak.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from enum import Enum, StrEnum

from agentscope.runtime._sbx_cli import SbxCli
from agentscope.runtime.errors import RuntimeContractError, SandboxClosedError, SandboxCreationError
from agentscope.runtime.requests import ExecRequest
from agentscope.runtime.results import ExecResult, ExecStatus
from agentscope.runtime.workspace import WorkspaceRoot, resolve_within

__all__ = ["NetworkPolicy", "SbxRuntimeConfig", "SbxSandboxRuntime"]

# sbx enforces a hard floor of 1 GiB regardless of the requested value.
_MIN_MEMORY_BYTES = 1024**3
_MEMORY_PATTERN = re.compile(r"^(?P<value>[0-9]+)(?P<unit>[mMgG])$")
_MEMORY_UNIT_MULTIPLIER = {"m": 1024**2, "g": 1024**3}

# Mirrors sbx's own `--name` validation: at least two characters, starting
# with a letter or number, containing only letters, numbers, hyphens, and
# periods; "default" is reserved by sbx.
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]+$")
_RESERVED_NAMES = frozenset({"default"})


class NetworkPolicy(StrEnum):
    """Network egress policy applied to a sandbox.

    Only ``DISABLED`` is supported in Phase 1A.1: package-registry access and
    dynamic allowlists are explicitly out of scope (see the Phase 1A.1 plan).
    """

    DISABLED = "disabled"


def _parse_memory_bytes(memory_limit: str) -> int:
    match = _MEMORY_PATTERN.match(memory_limit)
    if not match:
        raise RuntimeContractError(
            f"memory_limit must look like '<positive integer><m|g>', got {memory_limit!r}"
        )
    value = int(match.group("value"))
    if value <= 0:
        raise RuntimeContractError(f"memory_limit must be positive, got {memory_limit!r}")
    return value * _MEMORY_UNIT_MULTIPLIER[match.group("unit").lower()]


@dataclass(frozen=True, slots=True)
class SbxRuntimeConfig:
    """Typed, validated configuration for :class:`SbxSandboxRuntime`.

    Exposes only the ``sbx`` options AgentScope actually needs - not every
    flag the CLI supports. Carries no secret material: this config is safe to
    log, serialize, or include in telemetry attributes.
    """

    template: str | None = None
    cpu_limit: int = 1
    memory_limit: str = "1g"
    sandbox_name_prefix: str = "agentscope"
    network_policy: NetworkPolicy = NetworkPolicy.DISABLED
    create_timeout_s: float = 60.0
    default_command_timeout_s: float = 30.0
    cleanup_timeout_s: float = 30.0

    def __post_init__(self) -> None:
        if self.template is not None and not self.template.strip():
            raise RuntimeContractError("template must not be blank when provided")

        if self.cpu_limit <= 0:
            raise RuntimeContractError(f"cpu_limit must be > 0, got {self.cpu_limit!r}")

        memory_bytes = _parse_memory_bytes(self.memory_limit)
        if memory_bytes < _MIN_MEMORY_BYTES:
            raise RuntimeContractError(
                f"memory_limit must be >= 1 GiB (the sbx-enforced minimum), "
                f"got {self.memory_limit!r}"
            )

        if len(self.sandbox_name_prefix) < 2:
            raise RuntimeContractError(
                f"sandbox_name_prefix must be at least 2 characters, "
                f"got {self.sandbox_name_prefix!r}"
            )
        if not _NAME_PATTERN.match(self.sandbox_name_prefix):
            raise RuntimeContractError(
                "sandbox_name_prefix must start with a letter or number and contain "
                f"only letters, numbers, hyphens, and periods: {self.sandbox_name_prefix!r}"
            )
        if self.sandbox_name_prefix.lower() in _RESERVED_NAMES:
            raise RuntimeContractError(
                f"sandbox_name_prefix {self.sandbox_name_prefix!r} is reserved by sbx"
            )

        for field_name in ("create_timeout_s", "default_command_timeout_s", "cleanup_timeout_s"):
            if getattr(self, field_name) <= 0:
                raise RuntimeContractError(f"{field_name} must be > 0")


class _State(Enum):
    """Internal lifecycle state - never exposed; observed only via behavior."""

    READY = "ready"
    INVALID = "invalid"  # a command timed out; sandbox stopped, not yet removed
    CLOSED = "closed"  # removed (or never successfully created)


class SbxSandboxRuntime:
    """A ``SandboxRuntime`` backed by one persistent ``sbx`` sandbox.

    Lifecycle: ``NEW -> create (in __init__) -> READY -> execute* -> close()
    -> CLOSED``. There is no reachable "half-created" state: if sandbox
    creation fails, ``__init__`` raises and no instance is ever returned.

    A command timeout burns the whole sandbox rather than just that command
    (see docs/findings/sbx-cli.md): the spike proved that killing the local
    ``sbx exec`` process does not stop the remote command - only ``sbx stop``
    does. So ``execute()`` follows a timeout with ``sbx stop`` (best-effort)
    and moves to the ``INVALID`` state: no further ``execute()`` calls are
    accepted (``SandboxClosedError``), but ``close()`` still performs the
    final ``sbx rm -f`` when the caller eventually calls it. This is Case B
    from the plan's Step 9 - proven, not assumed, by the Step 1 spike.
    """

    def __init__(
        self,
        config: SbxRuntimeConfig,
        workspace: WorkspaceRoot,
        *,
        cli: SbxCli | None = None,
    ) -> None:
        self._config = config
        self._workspace = workspace
        self._cli = cli or SbxCli()
        self._name = f"{config.sandbox_name_prefix}-{uuid.uuid4().hex[:12]}"
        self._state = _State.READY
        self._create()

    @property
    def name(self) -> str:
        """The unique name of the underlying ``sbx`` sandbox."""
        return self._name

    @property
    def workspace(self) -> WorkspaceRoot:
        return self._workspace

    def _create(self) -> None:
        argv = SbxCli.build_create_argv(
            self._name,
            str(self._workspace.path),
            cpu_limit=self._config.cpu_limit,
            memory_limit=self._config.memory_limit,
            deny_network=self._config.network_policy is NetworkPolicy.DISABLED,
        )
        result = self._cli.run(argv, timeout_s=self._config.create_timeout_s)
        if result.error is not None or result.timed_out or result.returncode != 0:
            self._state = _State.CLOSED  # nothing was created; close() must not try to remove it
            detail = result.error or result.stderr.decode("utf-8", errors="replace").strip()
            raise SandboxCreationError(f"failed to create sandbox {self._name!r}: {detail}")

    def execute(self, request: ExecRequest) -> ExecResult:
        if self._state is not _State.READY:
            raise SandboxClosedError(f"sandbox {self._name!r} is closed or invalidated")

        timeout_s = (
            request.timeout_s
            if request.timeout_s is not None
            else self._config.default_command_timeout_s
        )

        absolute_cwd = resolve_within(self._workspace, request.cwd)
        argv = SbxCli.build_exec_argv(
            self._name, request.command, cwd=str(absolute_cwd), env=request.env
        )
        started_at = time.monotonic()
        cli_result = self._cli.run(argv, timeout_s=timeout_s)
        duration_s = time.monotonic() - started_at

        if cli_result.timed_out:
            # Killing the local `sbx exec` process (already done by the local
            # subprocess timeout) does not stop the remote command - only
            # `sbx stop` does (docs/findings/sbx-cli.md). Best-effort: even if
            # this itself fails, the runtime is still marked INVALID so no
            # caller can mistake it for a safe-to-reuse sandbox.
            self._cli.run(
                SbxCli.build_stop_argv(self._name), timeout_s=self._config.cleanup_timeout_s
            )
            self._state = _State.INVALID
            return ExecResult(
                status=ExecStatus.TIMED_OUT,
                message="command exceeded timeout_s",
                duration_s=duration_s,
            )
        if cli_result.error is not None:
            return ExecResult(
                status=ExecStatus.INFRA_FAILURE, message=cli_result.error, duration_s=duration_s
            )

        if cli_result.returncode is None:
            # Neither timed_out nor error was set, yet there is no exit code -
            # an sbx response shape we have not observed; treat it as an
            # infra failure rather than fabricating a COMPLETED result.
            return ExecResult(
                status=ExecStatus.INFRA_FAILURE,
                message="sbx exec returned no exit code",
                duration_s=duration_s,
            )

        stdout, stdout_truncated = _truncate(cli_result.stdout, request.max_output_bytes)
        stderr, stderr_truncated = _truncate(cli_result.stderr, request.max_output_bytes)
        return ExecResult(
            status=ExecStatus.COMPLETED,
            exit_code=cli_result.returncode,
            stdout=stdout,
            stderr=stderr,
            truncated=stdout_truncated or stderr_truncated,
            duration_s=duration_s,
        )

    def close(self) -> None:
        if self._state is _State.CLOSED:
            return
        self._cli.run(SbxCli.build_rm_argv(self._name), timeout_s=self._config.cleanup_timeout_s)
        self._state = _State.CLOSED


def _truncate(data: bytes, max_bytes: int) -> tuple[bytes, bool]:
    if len(data) <= max_bytes:
        return data, False
    return data[:max_bytes], True
