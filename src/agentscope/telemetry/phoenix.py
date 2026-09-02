"""Opt-in Arize Phoenix exporter setup (design 9).

This is the only module that imports the OpenTelemetry stack. It is imported
lazily and only by :mod:`agentscope.bootstrap` when telemetry is enabled, so the
deterministic test suite never pulls it into the import graph.

The pipeline is OTLP-over-HTTP built directly on the OpenTelemetry SDK - no
``grpcio`` and no ``arize-phoenix-otel`` dependency. Every attribute is run
through :class:`Sanitizer` before it reaches a span.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentscope.config.public import PublicConfig
from agentscope.config.secret import SecretConfig
from agentscope.telemetry.events import TelemetryEvent
from agentscope.telemetry.sanitizer import Sanitizer

__all__ = ["PhoenixSink", "configure_phoenix"]


class PhoenixSink:
    """A ``TelemetrySink`` that emits sanitized OpenTelemetry spans."""

    def __init__(self, tracer: Any, sanitizer: Sanitizer | None = None) -> None:
        self._tracer = tracer
        self._sanitizer = sanitizer or Sanitizer()

    def emit(self, event: TelemetryEvent) -> None:
        safe = self._sanitizer.sanitize_event(event)
        with self._tracer.start_as_current_span(safe.name) as span:
            for key, value in _flatten(safe.attributes):
                span.set_attribute(key, value)

    def record_exception(
        self, exc: BaseException, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        payload: dict[str, Any] = dict(attributes or {})
        safe = self._sanitizer.sanitize_event(
            TelemetryEvent(name="exception", attributes={**payload, "exception": exc})
        )
        with self._tracer.start_as_current_span("exception") as span:
            for key, value in _flatten(safe.attributes):
                span.set_attribute(key, value)


def configure_phoenix(public: PublicConfig, secret: SecretConfig) -> PhoenixSink:
    """Build a :class:`PhoenixSink` from validated configuration.

    Raises:
        ValueError: if telemetry is not enabled or no endpoint is configured.
    """
    if not public.telemetry_enabled or not public.telemetry_endpoint:
        raise ValueError("configure_phoenix requires telemetry_enabled and an endpoint")

    # Imported here so the default deterministic suite never imports OpenTelemetry.
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    headers: dict[str, str] | None = None
    if secret.otlp_headers is not None:
        headers = _parse_headers(secret.otlp_headers.get_secret_value())

    exporter = OTLPSpanExporter(endpoint=public.telemetry_endpoint, headers=headers)
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("agentscope.phase0.smoke")
    return PhoenixSink(tracer=tracer)


def _parse_headers(raw: str) -> dict[str, str]:
    """Parse ``k=v,k2=v2`` OTLP header strings into a mapping."""
    headers: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        headers[key.strip()] = value.strip()
    return headers


def _flatten(attributes: Mapping[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    flat: list[tuple[str, Any]] = []
    for key, value in attributes.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, Mapping):
            flat.extend(_flatten(value, prefix=f"{dotted}."))
        elif isinstance(value, (str, bool, int, float)):
            flat.append((dotted, value))
        else:
            flat.append((dotted, str(value)))
    return flat
