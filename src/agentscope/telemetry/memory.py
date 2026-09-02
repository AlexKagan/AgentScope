"""An in-memory telemetry sink for deterministic tests.

It stores *sanitized* events, mirroring the real export path so that tests
exercise sanitization exactly as production would.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentscope.telemetry.events import TelemetryEvent
from agentscope.telemetry.sanitizer import Sanitizer

__all__ = ["InMemorySink"]


class InMemorySink:
    """Collects sanitized events and exception records in a list."""

    def __init__(self, sanitizer: Sanitizer | None = None) -> None:
        self._sanitizer = sanitizer or Sanitizer()
        self.events: list[TelemetryEvent] = []

    def emit(self, event: TelemetryEvent) -> None:
        self.events.append(self._sanitizer.sanitize_event(event))

    def record_exception(
        self, exc: BaseException, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        payload: dict[str, Any] = {"exception": exc}
        if attributes:
            payload.update(attributes)
        self.events.append(
            self._sanitizer.sanitize_event(TelemetryEvent(name="exception", attributes=payload))
        )
