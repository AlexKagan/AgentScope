"""Opt-in Arize Phoenix smoke trace (design 9, 13.4).

Excluded from the default run. Enable with::

    uv run pytest -m phoenix

It needs AGENTSCOPE_TELEMETRY_ENDPOINT (and optionally AGENTSCOPE_PHOENIX_API_KEY
/ AGENTSCOPE_OTLP_HEADERS). The payload is entirely synthetic; no real provider
key is placed in span attributes.
"""

from __future__ import annotations

import os

import pytest

pytestmark = [pytest.mark.external, pytest.mark.phoenix]


@pytest.fixture
def endpoint() -> str:
    value = os.environ.get("AGENTSCOPE_TELEMETRY_ENDPOINT")
    if not value:
        pytest.skip("AGENTSCOPE_TELEMETRY_ENDPOINT not set")
    return value


def test_emits_one_sanitized_span(endpoint: str) -> None:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from agentscope.telemetry.events import TelemetryEvent
    from agentscope.telemetry.phoenix import PhoenixSink
    from agentscope.telemetry.sanitizer import REDACTED

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    sink = PhoenixSink(tracer=provider.get_tracer("agentscope.phase0.smoke"))

    sink.emit(
        TelemetryEvent(
            "phase0.smoke",
            {"synthetic": "ok", "note": "no real secrets here", "api_key": "should-be-redacted"},
        )
    )
    provider.force_flush()

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes is not None
    assert spans[0].attributes["api_key"] == REDACTED
    assert spans[0].attributes["synthetic"] == "ok"


def test_configure_phoenix_end_to_end(endpoint: str) -> None:
    from agentscope.config.public import PublicConfig
    from agentscope.config.secret import SecretConfig
    from agentscope.telemetry.events import TelemetryEvent
    from agentscope.telemetry.phoenix import configure_phoenix

    public = PublicConfig(telemetry_enabled=True, telemetry_endpoint=endpoint)  # type: ignore[call-arg]
    sink = configure_phoenix(public, SecretConfig())  # type: ignore[call-arg]
    sink.emit(TelemetryEvent("phase0.smoke", {"synthetic": "ok"}))
