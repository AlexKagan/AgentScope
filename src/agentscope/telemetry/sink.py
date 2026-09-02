"""The telemetry sink contract (design 9).

A sink accepts events and exceptions. Every implementation that exports data
outside the process MUST run it through :class:`agentscope.telemetry.sanitizer.Sanitizer`
first. Deterministic tests use the no-op or in-memory sinks.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from agentscope.telemetry.events import TelemetryEvent

__all__ = ["TelemetrySink"]


@runtime_checkable
class TelemetrySink(Protocol):
    """Receives sanitized telemetry from the platform."""

    def emit(self, event: TelemetryEvent) -> None:
        """Record a single event."""
        ...

    def record_exception(
        self, exc: BaseException, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        """Record an exception with optional extra attributes."""
        ...
