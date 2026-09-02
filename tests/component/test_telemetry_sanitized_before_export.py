"""Component test: seeded secrets are sanitized before export (design 13.2)."""

from __future__ import annotations

from agentscope.telemetry.events import TelemetryEvent
from agentscope.telemetry.memory import InMemorySink
from agentscope.telemetry.sanitizer import REDACTED


def test_emit_sanitizes_sensitive_attributes() -> None:
    sink = InMemorySink()
    sink.emit(
        TelemetryEvent(
            "model.call",
            {
                "authorization": "Bearer sk-FAKE-DEADBEEF-0000000000000000",
                "api_key": "sk-FAKE-DEADBEEF-0000000000000000",
                "prompt": "hi",
            },
        )
    )
    stored = sink.events[-1]
    assert stored.attributes["authorization"] == REDACTED
    assert stored.attributes["api_key"] == REDACTED
    assert stored.attributes["prompt"] == "hi"


def test_record_exception_scrubs_secret_in_message() -> None:
    sink = InMemorySink()
    sink.record_exception(RuntimeError("key=sk-FAKE-DEADBEEF-0000000000000000"))
    blob = repr(sink.events)
    assert "sk-FAKE-DEADBEEF-0000000000000000" not in blob


def test_no_seeded_secret_survives_in_sink_contents() -> None:
    sink = InMemorySink()
    sink.emit(TelemetryEvent("e", {"nested": {"token": "sk-FAKE-DEADBEEF-0000000000000000"}}))
    assert "sk-FAKE-DEADBEEF-0000000000000000" not in repr(sink.events)
