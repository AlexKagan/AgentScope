# `<package>` — <one-line purpose>

## Ownership
What this package is responsible for, and what it explicitly does **not** own
(cross-reference the design doc §12 table).

## Public contracts
The protocols, dataclasses, and functions other packages may import, with a
one-line contract for each. Everything else is private.

## Dependencies
- **Inward (allowed):** which other `agentscope` packages / contracts this one imports.
- **Outward (who imports this):** the packages expected to depend on it.
- **Third-party:** external libraries and why.

## Failure modes
The exceptions this package raises and the conditions that trigger them.

## Tests
Where the tests live (`tests/unit`, `tests/component`, `tests/contract`) and what
they assert.

## Telemetry
What, if anything, this package emits, and how it is sanitized.

## Security implications
Trust-boundary role: does it touch secrets, host env, host paths, or the
workspace? What invariant does it uphold?

## Deferred work
What is intentionally out of scope for Phase 0 and which later phase owns it.
