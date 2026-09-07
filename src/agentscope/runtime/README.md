# `runtime` — SandboxRuntime protocol and boundary policies

## Ownership
Owns the backend-independent `SandboxRuntime` protocol, the boundary-safe
request/result types, and the two boundary policies: sandbox-environment
construction by allowlist, and workspace path confinement.

Also owns `SbxRuntimeConfig` and `SbxSandboxRuntime` (Phase 1A.1): the
concrete `sbx` (Docker Sandboxes) backend, and the private `_sbx_cli.py`
boundary that invokes the local `sbx` binary.

## Public contracts
| Symbol | Contract |
|---|---|
| `SandboxRuntime` (Protocol) | `workspace: WorkspaceRoot`; `execute(ExecRequest) -> ExecResult`; `close() -> None` (idempotent — added Phase 1A.1, ADR 0004 amendment). No implicit host env, no unrestricted host path. |
| `ExecRequest` | Frozen. Non-empty `command`; workspace-relative `cwd` (no `..`, not absolute); requested `env` coerced to `str`→`str` and validated by the runtime; `timeout_s` is `float \| None` (`None` = the backend default); positive `max_output_bytes`. |
| `ExecResult` / `ExecStatus` | Frozen. `COMPLETED` carries `exit_code`; `TIMED_OUT` / `INFRA_FAILURE` must not. `truncated` flags output-limit hits. |
| `build_sandbox_environment` | Empty baseline (`SANDBOX_BASE_ENV` literals) + allowlisted requests only. Values literal, never interpolated. Never reads `os.environ`. |
| `reject_host_env_lookup` | Always raises — there is no model-facing "read host env var" capability. |
| `WorkspaceRoot` / `resolve_within` / `WorkspaceRelativePath` | Canonical workspace root; one validator that rejects absolute paths, `..`, and symlink escapes. |
| `SbxRuntimeConfig` / `NetworkPolicy` | Frozen. Validates resources, names, timeouts, and the environment allowlist. The serialized string `"disabled"` is normalized; every other network policy is rejected, so every constructible Phase 1A.1 configuration denies egress. Carries no secret material. |
| `SbxSandboxRuntime` | One persistent sandbox per instance. It validates requested environment variables itself and compensates failed creation with forced removal. A timeout returns `TIMED_OUT` only after stop or removal confirms termination; otherwise it returns `INFRA_FAILURE`. `close()` raises `SandboxCleanupError` on failure and remains retryable, transitioning to `CLOSED` only after confirmed removal. |
| `_sbx_cli.SbxCli` (private) | Argv-only boundary to the local `sbx` binary; never `shell=True`. `build_exec_argv` always emits `-e NAME=value` (never a bare `-e NAME`, which copies from the *local* process env - see findings). `build_create_argv` adds a sandbox-scoped `--deny-network "**"` whenever `deny_network=True` (the default) - confirmed to block all egress the same way as a global deny-all policy, but without depending on it. `build_stop_argv` / `build_rm_argv` build the rest of the lifecycle. Subprocess-level failures (missing binary, local timeout) are reported via `SbxCliResult` fields, never raised. |

## Dependencies
- **Inward:** none.
- **Outward:** Phase 1A Docker runtime; model-facing tools (Phase 1A).
- **Third-party:** none.

## Failure modes
`RuntimeContractError` (base `ValueError`) and its subclasses
`PathEscapeError`, `DisallowedEnvVarError`, `HostEnvLookupError`; and
`SandboxBackendError` (base `RuntimeError`, for sbx-backend infrastructure
failures with no `ExecResult` to carry them) and its subclasses
`SandboxCreationError`, `SandboxCleanupError`, `SandboxClosedError`.

**Step 13 (error normalization) status:** nonzero exit codes are normal
`ExecResult`s, not exceptions (Step 5); timeouts have distinct semantics via
`ExecStatus.TIMED_OUT` (Step 9); raw `subprocess`/`OSError` never escapes
`SbxCli.run` (Step 3); creation failures raise `SandboxCreationError`
(Step 4). **Known, documented gap:** a sandbox removed *externally* (not via
this runtime's own `close()`) cannot be told apart from a real command
exiting with the same code — `sbx exec` returns exit code `1` in both cases,
with no distinct, documented "sbx itself failed" exit code (unlike Docker's
125–127 convention). Detecting it would require parsing undocumented stderr
text; team decision was to document rather than build that fragile
dependency (`docs/findings/sbx-cli.md`,
`tests/external/test_sbx_error_normalization.py`). Does not affect
AgentScope's own lifecycle management — only matters if something outside
AgentScope interferes with a running sandbox.

## Tests
`tests/unit/test_environment_policy.py`, `test_workspace_path.py`,
`test_exec_types.py`, `test_sbx_config.py`, `test_sbx_cli.py`,
`test_sbx_sandbox_runtime.py`, `test_sbx_path_confinement.py`,
`test_sbx_timeout.py`; `tests/contract/test_sandbox_runtime_contract.py`
(Step 14: the `any_runtime` fixture runs the same protocol-conformance,
`execute()`, and idempotent-`close()` assertions against both
`FakeSandboxRuntime` and the real `SbxSandboxRuntime` - the `sbx` fixture
row is marked `external` + `sbx` and excluded from the default run, like
every other real-backend test).
A unit test greps `environment.py` to prove it never reads `os.environ`.
All of the `test_sbx_*.py` unit modules use a fake subprocess runner - no
real `sbx` needed. `test_sbx_sandbox_runtime.py` also covers what a
post-implementation audit found missing: `duration_s` is actually populated
(not silently `0.0`), `default_command_timeout_s` genuinely reaches `SbxCli`
when a request omits `timeout_s` (and a request override still wins),
`create_timeout_s`/`cleanup_timeout_s` reach their respective calls,
`max_output_bytes` truncation is correct and independent per stream, and a
missing `sbx` binary is handled correctly at both creation
(`SandboxCreationError`) and execute time (`ExecStatus.INFRA_FAILURE`, not
raised). `test_sbx_path_confinement.py` (Step 8) proves
absolute/`..` `cwd` never reaches `SbxSandboxRuntime` at all (rejected at
`ExecRequest` construction) and a `cwd` symlink escape is rejected by
`resolve_within` before any `sbx exec` call - and documents, as current
scope rather than a gap, that only `cwd` is checked this way; a symlink
named as a command *argument* is forwarded unexamined (verified safe anyway
by the real backend's mount isolation in `test_sbx_filesystem_isolation.py`).
`test_sbx_timeout.py` (Step 9) proves, against a scripted double, that a
command timeout issues `sbx stop` and moves the runtime to `INVALID`.

`tests/external/` (marked `external` + `sbx`, excluded from the default run
- `uv run pytest -m sbx`; requires `sbx login` and a global network policy
already initialized, `docs/findings/sbx-cli.md`) exercises the real `sbx`
backend:
- `test_sbx_execute.py` — stdout/stderr capture, exit-code fidelity, argument
  boundaries surviving real subprocess invocation, `cwd` handling,
  cross-command workspace sharing, and (post-audit) that `duration_s` is a
  real positive value, not the silent `0.0` every result used to carry.
- `test_sbx_environment_isolation.py` — a host-only secret is never inherited;
  an explicitly allowlisted variable does reach the sandbox.
- `test_sbx_filesystem_isolation.py` — only the mounted workspace is visible:
  sibling directories, `.env`, a source-tree sentinel, `..` traversal, and
  parent-directory listing are all confirmed unavailable, using a fixture
  deliberately outside the AgentScope repo. Also confirms (Step 8) that a
  symlink inside the workspace pointing outside it cannot be followed -
  the sandbox's own mount means the target path doesn't exist there at all.
- `test_sbx_timeout.py` (Step 9) — replicates the Step 1 spike's heartbeat
  methodology through the real `execute()` path: after a command times out,
  a continuously-updated file inside the workspace is confirmed to actually
  stop changing (not just that the local wait gave up), the runtime is
  confirmed unusable for further `execute()` calls afterward, and (post-audit)
  `close()` from that `INVALID` state is confirmed to actually remove the
  sandbox from `sbx ls` — not just the fake-backed version of that check.
- `test_sbx_resource_limits.py` (Step 10) — `cpu_limit`/`memory_limit` are
  confirmed actually applied (`nproc`, `/proc/meminfo`) through the real
  `SbxSandboxRuntime`, not just the raw CLI. Deliberately no OOM test.
- `test_sbx_network_isolation.py` (Step 11) — the sandbox-scoped deny-all
  policy blocks egress regardless of the machine's global policy, local
  command execution is unaffected, and no combination of `execute()`'s `env`
  can lift the block.
- `test_sbx_lifecycle.py` (Step 15) — create/reuse/close verified against
  the real backend through an independent channel (`sbx ls --json` run
  directly, not through our own `SbxCli`): exactly one sandbox is created,
  it persists (not recreated) across multiple `execute()` calls, and it's
  actually gone from `sbx ls` after `close()` (idempotent even then).
  Step 4's equivalent tests only ever used a scripted CLI double.
- `test_sbx_error_normalization.py` (Step 13) — documents, rather than
  papers over, the one confirmed gap in error normalization: an externally
  removed sandbox is indistinguishable from a real `exit 1` by exit code
  alone (see the Failure modes section above).

Full black-box security tests (path-attack argv forms) are Step 15.

## Telemetry
None emitted in Phase 0.

## Security implications
Upholds two invariants (design §8.5–8.6): the sandbox environment is built by
positive allowlisting from an empty baseline, and every model-facing path is
confined to the task workspace. Phase 0 proves these with policy tests; Phase 1A
adds black-box assertions from inside the real sandbox.

## CI
`.github/workflows/sbx-smoke.yml` runs the real `sbx` backend suite
(`uv run pytest -m sbx`) on a **self-hosted** runner labeled `[self-hosted,
sbx]` — GitHub-hosted `ubuntu-latest` runners don't reliably support the KVM
virtualization `sbx`'s Linux backend needs (unsupported/inconsistent nested
virtualization), so this deliberately does not run on standard hosted
runners. `workflow_dispatch` + a weekly informational schedule only — never
on `push`/`pull_request`, since it holds real Docker credentials
(`SBX_DOCKER_USERNAME` / `SBX_DOCKER_ACCESS_TOKEN` secrets, non-interactive
`sbx login --password-stdin`) and must never share a runner with untrusted
PR code. The `sbx` version is pinned (`EXPECTED_SBX_VERSION` in the
workflow) against `docs/findings/sbx-cli.md`'s verified behavior; the job
fails loudly on a version drift rather than silently testing against
unverified behavior. Cleans up (`sbx rm --all -f`, `sbx logout`) in an
`if: always()` step regardless of outcome. The default `ci.yml` remains
entirely `sbx`-free (`pytest`'s default `-m 'not external'`).

## Deferred work
Dynamic network allowlists and package-registry access remain out of scope
for Phase 1A.1 entirely (see the implementation plan).
