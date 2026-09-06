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
| `ExecRequest` | Frozen. Non-empty `command`; workspace-relative `cwd` (no `..`, not absolute); `env` coerced to `str`→`str` and assumed already filtered; positive `timeout_s` / `max_output_bytes`. |
| `ExecResult` / `ExecStatus` | Frozen. `COMPLETED` carries `exit_code`; `TIMED_OUT` / `INFRA_FAILURE` must not. `truncated` flags output-limit hits. |
| `build_sandbox_environment` | Empty baseline (`SANDBOX_BASE_ENV` literals) + allowlisted requests only. Values literal, never interpolated. Never reads `os.environ`. |
| `reject_host_env_lookup` | Always raises — there is no model-facing "read host env var" capability. |
| `WorkspaceRoot` / `resolve_within` / `WorkspaceRelativePath` | Canonical workspace root; one validator that rejects absolute paths, `..`, and symlink escapes. |
| `SbxRuntimeConfig` / `NetworkPolicy` | Frozen. Validates `cpu_limit > 0`; `memory_limit` matches `<int><m\|g>` and is `>= 1 GiB` (the `sbx`-enforced floor, see `docs/findings/sbx-cli.md`); `sandbox_name_prefix` follows `sbx`'s own name rules (>=2 chars, starts alnum, `[A-Za-z0-9.-]`, not `"default"`); all timeouts `> 0`. Carries no secret material. |
| `SbxSandboxRuntime` | One persistent `sbx` sandbox per instance: created eagerly in `__init__` (raises `SandboxCreationError` on failure — no half-created state), reused across every `execute()`, released by `close()` (idempotent). `execute()` translates the workspace-relative `cwd` via `resolve_within` before handing it to `sbx exec -w`. Internal states: `READY` → (on any command timeout) `INVALID` → (on `close()`) `CLOSED`. A timeout runs `sbx stop` (the only thing proven to actually kill the remote command — see findings) and moves to `INVALID`: further `execute()` calls raise `SandboxClosedError`, but `close()` still performs the real `sbx rm -f` and remains idempotent. |
| `_sbx_cli.SbxCli` (private) | Argv-only boundary to the local `sbx` binary; never `shell=True`. `build_exec_argv` always emits `-e NAME=value` (never a bare `-e NAME`, which copies from the *local* process env - see findings). `build_create_argv` / `build_stop_argv` / `build_rm_argv` build the rest of the lifecycle. Subprocess-level failures (missing binary, local timeout) are reported via `SbxCliResult` fields, never raised. |

## Dependencies
- **Inward:** none.
- **Outward:** Phase 1A Docker runtime; model-facing tools (Phase 1A).
- **Third-party:** none.

## Failure modes
`RuntimeContractError` (base `ValueError`) and its subclasses
`PathEscapeError`, `DisallowedEnvVarError`, `HostEnvLookupError`; and
`SandboxBackendError` (base `RuntimeError`, for sbx-backend infrastructure
failures with no `ExecResult` to carry them) and its subclasses
`SandboxCreationError`, `SandboxClosedError`. Full error-hierarchy
normalization (mapping every `sbx`/subprocess failure mode) is Step 13.

## Tests
`tests/unit/test_environment_policy.py`, `test_workspace_path.py`,
`test_exec_types.py`, `test_sbx_config.py`, `test_sbx_cli.py`,
`test_sbx_sandbox_runtime.py`, `test_sbx_path_confinement.py`,
`test_sbx_timeout.py`; `tests/contract/test_sandbox_runtime_contract.py`.
A unit test greps `environment.py` to prove it never reads `os.environ`.
All of the `test_sbx_*.py` unit modules use a fake subprocess runner - no
real `sbx` needed. `test_sbx_path_confinement.py` (Step 8) proves
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
  boundaries surviving real subprocess invocation, `cwd` handling, and
  cross-command workspace sharing.
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
  stop changing (not just that the local wait gave up), and the runtime is
  confirmed unusable for further `execute()` calls afterward.

Full black-box security tests (path-attack argv forms, network) are Step 15.

## Telemetry
None emitted in Phase 0.

## Security implications
Upholds two invariants (design §8.5–8.6): the sandbox environment is built by
positive allowlisting from an empty baseline, and every model-facing path is
confined to the task workspace. Phase 0 proves these with policy tests; Phase 1A
adds black-box assertions from inside the real sandbox.

## Deferred work
CPU/memory limits are already passed to `sbx create` (`SbxRuntimeConfig`,
Step 2/4); black-box verification that they're actually applied is Step 10.
Network isolation is Step 11.

**Known gap (Step 6, deliberately deferred):** `SANDBOX_BASE_ENV["HOME"]` is
`"/workspace"`, but the real `sbx` backend mounts the workspace at its own
host-mirrored absolute path — `/workspace` does not exist inside a real
sandbox at all (see `docs/findings/sbx-cli.md`). Nothing currently wires
`build_sandbox_environment()`'s output into `SbxSandboxRuntime`, so this is
latent, not active. Whoever adds that wiring must not forward `HOME`
unconditionally for this backend.
