"""The telemetry event value type."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = ["TelemetryEvent"]


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    """A named event plus a flat-or-nested attribute mapping."""

    name: str
    attributes: Mapping[str, Any] = field(default_factory=dict)
