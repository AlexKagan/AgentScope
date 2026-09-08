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
| `Platform` | Frozen shell containing `config`, architecture `registry`, `telemetry`, and the live model `models` registry (repr-suppressed). |
| `build_platform(public, secret, *, registry=None, model_adapter_factory=None, telemetry_factory=None)` | Composes a `Platform`. A model-free config constructs no adapters; a model-enabled config constructs and registers both `regular` and `fast` slots. |
| `ModelAdapterFactory` (Protocol) | `(ModelDefinition, api_key: str) -> ModelAdapter`. The seam where a raw key becomes a narrow capability. |
| `default_model_adapter_factory` | Lazily constructs the LangChain `OpenAICompatibleChatAdapter`; provider I/O starts only on `ainvoke`. |

## Dependencies
- **Inward:** `config`, `models`, `architectures`, `telemetry`.
- **Outward:** application entrypoints (Phase 1A+).
- **Third-party:** none directly.

## Failure modes
`MissingSecretError` when a required credential is absent;
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
Real secret-store integration and dynamic credential rotation.
