# `config` — typed public and secret settings

## Ownership
Owns the typed configuration surface: validated non-secret settings
(`PublicConfig`), the credential carrier (`SecretConfig`), TOML loading, and the
safe-serialization rules. Model definitions use fixed purpose slots and live in
`agentscope.models`.

Does **not** own provider-client construction (that is `bootstrap`) or any
runtime behavior.

## Public contracts
| Symbol | Contract |
|---|---|
| `PublicConfig` | Validated, frozen, JSON-serializable non-secret config. `safe_dump()` is the sanctioned snapshot. Holds no credentials. |
| `SecretConfig` | `SecretStr` fields only. `require(field)` returns a plaintext value or raises `MissingSecretError`. `safe_dump()` returns `{field: "REDACTED"}`. **Not re-exported from `agentscope.config`** — import from `agentscope.config.secret`. |
| `load_public_config` | Load and validate typed public configuration from TOML without consulting `.env`. |
| `RuntimeMode`, `Limits` | Public enums/among limits used by the runtime layer. |

## Phase 1A.2 model configuration revision

The finalized operator-facing contract uses two purpose-based model slots:
`models.regular` and `models.fast`. The slot says how AgentScope uses the model;
it does not encode the provider. Either slot can use any supported provider,
and both can use the same model with different parameters.

TOML parameters follow presence semantics: omission means “use the provider/model
default.” TOML does not support `key =` or native `null`, and an empty string is
not a default marker. Reasoning therefore has explicit `provider_default`,
`disabled`, and `enabled` modes. Portable options belong in `parameters`;
additional provider fields belong in a validated and fingerprinted
`provider_options` escape hatch.

The complete canonical TOML and validation rules are in
`docs/plans/phase-1a.2-model-usage-cost.md` §7.1.

## Dependencies
- **Inward:** none (leaf package).
- **Outward:** `bootstrap` (both classes), `telemetry.phoenix` (`SecretConfig` for OTLP headers), everything else (`PublicConfig` only).
- **Third-party:** `pydantic`, `pydantic-settings`.

## Failure modes
`pydantic.ValidationError` on invalid public config or model slots;
`MissingSecretError` from `SecretConfig.require`.

## Tests
`tests/unit/test_public_config.py` and `test_secret_config.py`. Assert validation,
deep immutability, and that no seeded fake secret appears in any representation.

## Telemetry
None emitted.

## Security implications
`SecretConfig` is the single structured credential carrier. Isolation is
enforced by: `SecretStr` redaction, no re-export from the package root, and
`tests/component/test_no_secretconfig_outside_bootstrap.py`.

## Deferred work
Secret-store vendor integration and dynamic rotation (deferred, see design §18).
