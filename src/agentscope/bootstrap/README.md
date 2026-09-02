# `bootstrap` — composition root

## Ownership
Owns platform composition: it loads `PublicConfig` + `SecretConfig`, turns
credentials into constructed clients and telemetry exporters, and injects those
into a `Platform`. It is the **only** package permitted to consume
`SecretConfig`.

Does **not** own agent topology or any model-visible state.

## Public contracts
| Symbol | Contract |
|---|---|
| `Platform` | Frozen: `config`, `registry`, `telemetry`, `model_client` (repr-suppressed). |
| `build_platform(public, secret, *, registry=None, model_client_factory=None, telemetry_factory=None)` | Composes a `Platform`. `NoOpSink` unless telemetry is enabled; model client built only when `primary_model` is set; missing key raises `MissingSecretError` at bootstrap. |
| `ModelClientFactory` (Protocol) | `(ModelIdentifier, api_key: str) -> object`. The seam where a raw key becomes a narrow capability. |
| `default_model_client_factory` | Phase 0 placeholder — raises `NotImplementedError` (model invocation is Phase 1A). |

## Dependencies
- **Inward:** `config`, `architectures`, `telemetry`.
- **Outward:** application entrypoints (Phase 1A+).
- **Third-party:** none directly.

## Failure modes
`MissingSecretError` when a required credential is absent;
`NotImplementedError` from the default model-client factory;
`ValueError` from `configure_phoenix` when misconfigured.

## Tests
`tests/component/test_composition_root.py`,
`test_public_snapshot_no_secrets.py`,
`test_startup_without_credentials.py`,
`test_no_secretconfig_outside_bootstrap.py`.

## Telemetry
Constructs the telemetry sink; emits nothing itself.

## Security implications
The trust boundary. Raw secrets are consumed only here and converted into
injected capabilities. Enforced by the static-scan test that forbids
`SecretConfig` references elsewhere.

## Deferred work
Model-provider adapters and their credential requirements (Phase 1A); real
secret-store integration (deferred).
