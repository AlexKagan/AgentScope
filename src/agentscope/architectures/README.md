# `architectures` — contract, identity, registry

## Ownership
Owns the minimal `AgentArchitecture` contract, the stable identity fields
(`architecture_key`, `architecture_version`), and the `ArchitectureRegistry`
skeleton that resolves keys to implementations or factories.

Does **not** own shared runtime implementations or any concrete architecture.

## Public contracts
| Symbol | Contract |
|---|---|
| `AgentArchitecture` (Protocol, runtime-checkable) | Exposes `identity: ArchitectureIdentity` and `describe() -> str`. No execution surface in Phase 0. |
| `ArchitectureIdentity` | Frozen; `architecture_key` matches `^[a-z][a-z0-9_]*$`, `architecture_version` is `MAJOR.MINOR.PATCH`. |
| `ArchitectureRegistry` | `register` / `register_factory` reject duplicates (`DuplicateArchitectureError`); `resolve` raises `UnknownArchitectureError` on a miss and caches factory output; `keys()` is sorted (deterministic). No global singleton. |

## Dependencies
- **Inward:** none.
- **Outward:** `bootstrap` (holds one registry instance).
- **Third-party:** none.

## Failure modes
`ValueError` from `ArchitectureIdentity` validation;
`DuplicateArchitectureError` / `UnknownArchitectureError` from the registry.

## Tests
`tests/unit/test_architecture_identity.py`,
`tests/unit/test_architecture_registry.py`,
`tests/contract/test_architecture_contract.py`.

## Telemetry
None emitted.

## Security implications
None directly. Identity fields exist so later evaluation can attribute
behavior changes to the architecture rather than the model, prompt, or runtime.

## Deferred work
`build()` / execution seams, graph DSL, YAML topology — all deferred (design §3).
