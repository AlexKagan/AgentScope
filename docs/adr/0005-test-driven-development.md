# ADR 0005 — Test-driven development for core behavior

## Status
Accepted (Phase 0).

## Context
Phase 0 delivers contracts and security invariants, not features. These are
exactly the things that rot silently without executable checks.

## Decision
Core behavior is built red → green → refactor. Tests are split into
`tests/unit`, `tests/component`, `tests/contract`, and `tests/external`.
External/`phoenix`-marked tests are excluded from the default run and from
deterministic CI. The default suite passes with no Docker, no Phoenix, and no
model credentials.

## Consequences
- Every security invariant has a test at the earliest honest layer.
- CI secrets are never passed to tests that would launch untrusted sandbox code.
