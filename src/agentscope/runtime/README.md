# `runtime` — SandboxRuntime protocol and boundary policies

## Ownership
Owns the backend-independent `SandboxRuntime` protocol, the boundary-safe
request/result types, and the two boundary policies: sandbox-environment
construction by allowlist, and workspace path confinement.

Does **not** own any concrete sandbox backend. Docker Sandboxes implement the
protocol in Phase 1A.

## Public contracts
| Symbol | Contract |
|---|---|
| `SandboxRuntime` (Protocol) | `workspace: WorkspaceRoot`; `execute(ExecRequest) -> ExecResult`. No implicit host env, no unrestricted host path. |
| `ExecRequest` | Frozen. Non-empty `command`; workspace-relative `cwd` (no `..`, not absolute); `env` coerced to `str`→`str` and assumed already filtered; positive `timeout_s` / `max_output_bytes`. |
| `ExecResult` / `ExecStatus` | Frozen. `COMPLETED` carries `exit_code`; `TIMED_OUT` / `INFRA_FAILURE` must not. `truncated` flags output-limit hits. |
| `build_sandbox_environment` | Empty baseline (`SANDBOX_BASE_ENV` literals) + allowlisted requests only. Values literal, never interpolated. Never reads `os.environ`. |
| `reject_host_env_lookup` | Always raises — there is no model-facing "read host env var" capability. |
| `WorkspaceRoot` / `resolve_within` / `WorkspaceRelativePath` | Canonical workspace root; one validator that rejects absolute paths, `..`, and symlink escapes. |

## Dependencies
- **Inward:** none.
- **Outward:** Phase 1A Docker runtime; model-facing tools (Phase 1A).
- **Third-party:** none.

## Failure modes
`RuntimeContractError` (base `ValueError`) and its subclasses
`PathEscapeError`, `DisallowedEnvVarError`, `HostEnvLookupError`.

## Tests
`tests/unit/test_environment_policy.py`, `test_workspace_path.py`,
`test_exec_types.py`; `tests/contract/test_sandbox_runtime_contract.py`.
A unit test greps `environment.py` to prove it never reads `os.environ`.

## Telemetry
None emitted in Phase 0.

## Security implications
Upholds two invariants (design §8.5–8.6): the sandbox environment is built by
positive allowlisting from an empty baseline, and every model-facing path is
confined to the task workspace. Phase 0 proves these with policy tests; Phase 1A
adds black-box assertions from inside the real sandbox.

## Deferred work
Concrete Docker backend, verified process termination / resource limits /
network isolation / mount behavior — Phase 1A/2.
