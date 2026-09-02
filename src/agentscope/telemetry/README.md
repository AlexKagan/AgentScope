# `telemetry` — sink contract, sanitizer, exporters

## Ownership
Owns the `TelemetrySink` contract, the mandatory `Sanitizer`, the deterministic
`NoOpSink` (default) and `InMemorySink` (tests), and the opt-in Arize Phoenix
exporter setup.

Does **not** own business or architecture control flow.

## Public contracts
| Symbol | Contract |
|---|---|
| `TelemetrySink` (Protocol) | `emit(TelemetryEvent)`, `record_exception(exc, *, attributes=None)`. Any exporter runs `Sanitizer` first. |
| `TelemetryEvent` | Frozen `name` + `attributes` mapping (may be nested). |
| `Sanitizer` | Redacts credential-named keys, recurses mappings/sequences, sanitizes exception type/message/args, length-limits values, fails closed (drops, never partially logs). |
| `NoOpSink` | Discards everything. Wired when `telemetry_enabled` is false. |
| `InMemorySink` | Stores **sanitized** events for assertions. |
| `configure_phoenix` (in `.phoenix`, not re-exported) | Builds a `PhoenixSink` over an OTel tracer. Imports the OTel stack lazily; called only by `bootstrap`. |

## Dependencies
- **Inward:** `config` (`PublicConfig`, `SecretConfig` — only in `phoenix.py`).
- **Outward:** `bootstrap`.
- **Third-party:** `pydantic` (SecretStr detection); `opentelemetry-*`, `arize-phoenix-otel` (only inside `phoenix.py`, imported lazily).

## Failure modes
`configure_phoenix` raises `ValueError` if telemetry is disabled or no endpoint
is set. Sanitization never raises on unexpected value types — it redacts.

## Tests
`tests/unit/test_sanitizer.py`;
`tests/component/test_telemetry_sanitized_before_export.py`;
`tests/external/test_phoenix_smoke.py` (marked `phoenix`, opt-in).

## Telemetry
This package *is* the telemetry boundary. Everything exported is sanitized.

## Security implications
Enforces design §9: all telemetry passes `Sanitizer` before export. Pattern
redaction is defense in depth; the primary control is keeping secrets out of
`TelemetryEvent` in the first place. The Phoenix smoke test uses a synthetic
non-secret payload.

## Deferred work
Full span/metric instrumentation and trace-context propagation — later phases.
