# ADR 0009 — Sanitize all telemetry before export

## Status
Accepted (Phase 0).

## Context
Traces and logs are exported and durable. A secret that reaches a span attribute
is effectively published.

## Decision
Every `TelemetrySink` that exports data runs payloads through `Sanitizer` first.
The sanitizer redacts credential-named keys, recurses mappings and sequences,
sanitizes exception type/message/args, length-limits values, and fails closed
(known-sensitive values are dropped, never partially logged). `InMemorySink`
also sanitizes, so tests exercise the real path.

Pattern redaction is **defense in depth**. The primary control is ADR 0006/0007:
secrets never enter a `TelemetryEvent`.

## Consequences
- The Phoenix smoke test uses a synthetic non-secret payload and still asserts
  a seeded sensitive key is redacted on the export path.
- A benign key holding a secret-shaped value is also scrubbed.
