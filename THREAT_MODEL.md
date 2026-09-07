# AgentScope Threat Model — Phase 0 baseline + Phase 1A.1 verification

This document covers the Phase 0 foundation plus Phase 1A.1's concrete `sbx`
(Docker Sandboxes) backend. Phase 0 established the boundary policies and
proved them with fakes; Phase 1A.1 proves the same guarantees empirically
against the real sandbox (`docs/findings/sbx-cli.md`,
`src/agentscope/runtime/README.md`). Guarantees not yet backed by a real
implementation (e.g. anything beyond `execute()` — file operations, package
installation) remain called out as deferred.

## Assets

- Provider API keys and telemetry credentials (`SecretConfig`).
- The host environment and host filesystem (AgentScope source, `.env`,
  credential stores, service-account mounts, the user's home directory).
- Integrity of exported telemetry, logs, and (later) run records.

## Actors

- **Trusted:** the AgentScope host process, the composition root, authenticated
  provider/telemetry clients.
- **Untrusted:** the model, all code the model causes to execute, the task
  workspace contents, the sandbox process and its environment. The model
  provider is trusted; the model's *output and effects* are not.

## Trust boundaries

| Area | Trust level | Raw secrets? | Model-accessible? |
|---|---|---|---|
| Composition root | Trusted | Yes, transiently | No |
| Authenticated clients | Trusted | Internally | Only narrow capabilities |
| Public configuration | Trusted / non-secret | No | Selected safe fields |
| Architecture / graph state | Untrusted for secret handling | No | Yes |
| Task workspace | Untrusted | No | Yes |
| Sandbox process / environment | Untrusted | No | Yes |
| Logs, traces, run records | Exported / durable | No | Indirectly inspectable |

## Threats, controls, verification

| Threat | Primary control | Defense in depth | Verification |
|---|---|---|---|
| Host environment leakage into the sandbox | `SbxSandboxRuntime.execute()` enforces an empty-baseline positive allowlist | Non-allowlisted names are rejected at the concrete runtime boundary; the policy never reads `os.environ`; `sbx exec` receives explicit `NAME=value`, never bare `-e NAME` | Phase 0 unit (`test_environment_policy.py`); Phase 1A.1 unit and real-backend black-box (`test_sbx_sandbox_runtime.py`, `tests/external/test_sbx_environment_isolation.py`) |
| `.env` / host file exposure | Workspace-only mount; model-facing APIs take no host paths | One path-confinement validator: reject absolute, `..`, symlink escape (`resolve_within`, applied to `cwd` before any `sbx` call) | Phase 0 policy tests (`test_workspace_path.py`); Phase 1A.1 real-backend black-box (`tests/external/test_sbx_filesystem_isolation.py`, `tests/unit/test_sbx_path_confinement.py`) |
| Secret in model context / durable state | Inject constructed clients, not keys; `SecretConfig` not re-exported | Live deps kept out of serializable state (ADR 0003); `Platform.model_client` repr-suppressed | Phase 0 (`test_no_secretconfig_outside_bootstrap.py`, `test_public_snapshot_no_secrets.py`) |
| Secret in trace / log / error | Prevent entry: secrets never put into `TelemetryEvent` | Recursive `Sanitizer`, fail-closed; `SecretStr` redaction; exception scrubbing | Phase 0 (`test_sanitizer.py`, `test_telemetry_sanitized_before_export.py`) |
| Prompt-injected exfiltration via network | Sandbox-scoped `--deny-network "**"` at creation (ADR-less, `docs/findings/sbx-cli.md`) — does not depend on the host machine's own global network policy | No credentials placed in the sandbox environment (see above); tool policy + approvals remain a later-phase concern | Phase 1A.1 black-box HTTP, raw TCP, and host-loopback tests (`tests/external/test_sbx_network_isolation.py`) |
| Runaway/malicious process outlasting its command timeout | `execute()` returns `TIMED_OUT` only after `sbx stop` or forced removal confirms termination (ADR 0011) | If neither succeeds, the outcome is `INFRA_FAILURE`, cleanup stays retryable, and the runtime is non-reusable | Phase 1A.1 fault-injection unit tests and real-backend heartbeat test (`test_sbx_timeout.py`) |
| Agent requests a host env lookup | No such model-facing capability (`reject_host_env_lookup` always raises) | Agent-supplied env values are literal, never interpolated | Phase 0 (`test_environment_policy.py`) |
| Malicious workspace symlink | Canonical workspace confinement (`resolve()` collapses links before the containment check) applied to `cwd` | Sandbox mount isolation as a second layer — confirmed the symlink's host-path target does not exist inside the sandbox at all, so even a symlink named as a command *argument* (not checked by `resolve_within`) cannot be followed | Phase 0 (`test_workspace_path.py`); Phase 1A.1 real-backend black-box (`tests/unit/test_sbx_path_confinement.py`, `tests/external/test_sbx_filesystem_isolation.py`) |
| Accidental secret commit | `.gitignore` excludes `.env` / `.env.*`; `.env.example` placeholders only | gitleaks in pre-commit + CI (ADR 0010) | Phase 0 (`test_repo_hygiene.py`) |

## Secret isolation invariant (release gate)

> Credentials are available only to trusted infrastructure components that
> require them. They are never placed in model context, durable state,
> model-visible tool arguments or results, the task workspace, the sandbox
> environment, logs, telemetry, evaluation records, or error messages. The
> sandbox receives an explicit allowlisted environment and never inherits the
> host environment.

This is a release gate, verified by the Phase 0 tests listed above and, for
the real `sbx` backend, by the Phase 1A.1 tests listed above.

## Residual risk

Anything intentionally placed in the task workspace is visible to the agent and
the sandbox. Secret isolation does **not** make arbitrary workspace contents
confidential from the model.

Phase 1A.1 proved real process termination (via `sbx stop` on timeout),
resource limits (CPU/memory), network isolation, and mount/filesystem
isolation against the actual `sbx` backend — these are no longer just Phase 0
policy claims backed by fakes. Two specific, deliberately accepted gaps
remain, both documented rather than silently assumed away:

- **Symlinked command arguments aren't checked by `resolve_within`** — only
  `cwd` is. Verified safe in practice (the sandbox's own mount means the
  symlink's target doesn't exist inside it), but this is a property of the
  current `sbx` backend's mount behavior, not of AgentScope's own validation
  layer. See `tests/unit/test_sbx_path_confinement.py`.
- **A sandbox removed externally (not via its owning runtime's `close()`)
  cannot be distinguished from a real command exiting with the same code** —
  `sbx exec` returns exit code `1` in both cases, with no distinct
  "infrastructure failure" exit code. Detecting it reliably would require
  parsing undocumented CLI stderr text; documented as a known gap rather than
  built as a fragile dependency. Does not affect AgentScope's own lifecycle
  management. See `docs/findings/sbx-cli.md` and
  `tests/external/test_sbx_error_normalization.py`.

Beyond the runtime itself, file operations (`read_file`/`write_file`/etc.),
package installation policy, and dynamic network allowlists remain
out of scope for Phase 1A.1 entirely (see the implementation plan) and are
Phase 1A/2 acceptance concerns.
