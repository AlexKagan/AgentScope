# ADR 0007 — Raw secrets stay in the composition root

## Status
Accepted (Phase 0).

## Context
The fewer components that touch raw credentials, the smaller the security-review
surface and the leak surface.

## Decision
Only `agentscope.bootstrap` consumes `SecretConfig`. It constructs authenticated
clients and telemetry exporters from secrets and injects those constructed
dependencies. Every other component receives the narrowest capability it needs —
never `SecretConfig`, never the full settings object, never host-env access.
`telemetry.phoenix` is a narrow, listed exception: it reads only the OTLP
headers to build the exporter, and is invoked only by `bootstrap`.

Enforced by `tests/component/test_no_secretconfig_outside_bootstrap.py`, which
scans every source file.

## Consequences
- `ModelClientFactory` is the seam where a raw key becomes a narrow capability.
- Adding a new secret consumer is a deliberate, reviewed change to the allowlist.
