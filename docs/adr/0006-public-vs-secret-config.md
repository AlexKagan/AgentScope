# ADR 0006 — Separate public configuration from secret configuration

## Status
Accepted (Phase 0).

## Context
If credentials and safe settings share one object, that object cannot be logged,
snapshotted, or put in a trace without leaking secrets — so nothing is.

## Decision
Two separate classes:
- `PublicConfig` — validated, frozen, JSON-serializable, credential-free.
  `safe_dump()` is the sanctioned snapshot.
- `SecretConfig` — `SecretStr` fields only; not re-exported from
  `agentscope.config`; `require()` for controlled plaintext access.

Public model configuration may name a provider/model (`openai:gpt-x`); the
matching API key belongs only to `SecretConfig`.

## Consequences
- `PublicConfig` can be freely serialized.
- The set of code paths that see raw credentials is small and greppable.
