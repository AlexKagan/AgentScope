"""The default telemetry sink: does nothing, deterministically."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agentscope.telemetry.events import TelemetryEvent

__all__ = ["NoOpSink"]


class NoOpSink:
    """A ``TelemetrySink`` that discards everything. Used when telemetry is off."""

    def emit(self, event: TelemetryEvent) -> None:
        """Discard the event."""

    def record_exception(
        self, exc: BaseException, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        """Discard the exception."""
