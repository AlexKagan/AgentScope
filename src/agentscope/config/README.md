# `config` — typed public and secret settings

## Ownership
Owns the typed configuration surface: validated non-secret settings
(`PublicConfig`), the credential carrier (`SecretConfig`), the `provider:name`
model-identifier parser, and the safe-serialization rules.

Does **not** own provider-client construction (that is `bootstrap`) or any
runtime behavior.

## Public contracts
| Symbol | Contract |
|---|---|
| `PublicConfig` | Validated, frozen, JSON-serializable non-secret config. `safe_dump()` is the sanctioned snapshot. Holds no credentials. |
| `SecretConfig` | `SecretStr` fields only. `require(field)` returns a plaintext value or raises `MissingSecretError`. `safe_dump()` returns `{field: "REDACTED"}`. **Not re-exported from `agentscope.config`** — import from `agentscope.config.secret`. |
| `ModelIdentifier` / `parse_model_identifier` | Parse/validate `provider:name`; reject whitespace and credential-shaped values. |
| `RuntimeMode`, `Limits` | Public enums/among limits used by the runtime layer. |

## Dependencies
- **Inward:** none (leaf package).
- **Outward:** `bootstrap` (both classes), `telemetry.phoenix` (`SecretConfig` for OTLP headers), everything else (`PublicConfig` only).
- **Third-party:** `pydantic`, `pydantic-settings`.

## Failure modes
`pydantic.ValidationError` on invalid public config; `ValueError` from
`parse_model_identifier`; `MissingSecretError` from `SecretConfig.require`.

## Tests
`tests/unit/test_public_config.py`, `test_secret_config.py`,
`test_model_identifier.py`. Assert validation, frozen-ness, and that no seeded
fake secret appears in any representation.

## Telemetry
None emitted.

## Security implications
`SecretConfig` is the single structured credential carrier. Isolation is
enforced by: `SecretStr` redaction, no re-export from the package root, and
`tests/component/test_no_secretconfig_outside_bootstrap.py`.

## Deferred work
Secret-store vendor integration and dynamic rotation (deferred, see design §18).
