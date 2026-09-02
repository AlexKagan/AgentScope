# AgentScope Threat Model — Phase 0 baseline

This document covers the Phase 0 foundation. Runtime-level guarantees (real
sandbox isolation, network controls, resource limits) are Phase 1A/2 and are
called out as such.

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
| Host environment leakage into the sandbox | Empty-baseline sandbox env + positive allowlist (`build_sandbox_environment`) | Non-allowlisted names dropped/rejected; module never reads `os.environ` | Phase 0 unit (`test_environment_policy.py`); Phase 1A black-box |
| `.env` / host file exposure | Workspace-only mount; model-facing APIs take no host paths | One path-confinement validator: reject absolute, `..`, symlink escape | Phase 0 policy tests (`test_workspace_path.py`); Phase 1A black-box |
| Secret in model context / durable state | Inject constructed clients, not keys; `SecretConfig` not re-exported | Live deps kept out of serializable state (ADR 0003); `Platform.model_client` repr-suppressed | Phase 0 (`test_no_secretconfig_outside_bootstrap.py`, `test_public_snapshot_no_secrets.py`) |
| Secret in trace / log / error | Prevent entry: secrets never put into `TelemetryEvent` | Recursive `Sanitizer`, fail-closed; `SecretStr` redaction; exception scrubbing | Phase 0 (`test_sanitizer.py`, `test_telemetry_sanitized_before_export.py`) |
| Prompt-injected exfiltration | No credentials in the sandbox; network disabled by default (Phase 1A runtime) | Tool policy + approvals (later phases) | Phase 1A/2 |
| Agent requests a host env lookup | No such model-facing capability (`reject_host_env_lookup` always raises) | Agent-supplied env values are literal, never interpolated | Phase 0/1A |
| Malicious workspace symlink | Canonical workspace confinement (`resolve()` collapses links before the containment check) | Sandbox mount isolation | Phase 0/1A |
| Accidental secret commit | `.gitignore` excludes `.env` / `.env.*`; `.env.example` placeholders only | gitleaks in pre-commit + CI (ADR 0010) | Phase 0 (`test_repo_hygiene.py`) |

## Secret isolation invariant (release gate)

> Credentials are available only to trusted infrastructure components that
> require them. They are never placed in model context, durable state,
> model-visible tool arguments or results, the task workspace, the sandbox
> environment, logs, telemetry, evaluation records, or error messages. The
> sandbox receives an explicit allowlisted environment and never inherits the
> host environment.

This is a release gate, verified by the Phase 0 tests listed above.

## Residual risk

Anything intentionally placed in the task workspace is visible to the agent and
the sandbox. Secret isolation does **not** make arbitrary workspace contents
confidential from the model. Phase 0 fakes do not prove real process
termination, resource limits, network isolation, or mount behavior — those are
Phase 1A/2 acceptance concerns.
