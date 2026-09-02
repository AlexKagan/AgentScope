"""Telemetry sanitization (design 9).

Pattern redaction here is *defense in depth*. The primary control is preventing
secrets from ever entering a :class:`TelemetryEvent`. This sanitizer:

* redacts values whose key names match credential categories,
* recurses through nested mappings and sequences,
* sanitizes exception type, message, and args,
* length-limits large values,
* fails closed for known-sensitive keys (value dropped, never partially logged).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import SecretStr

from agentscope.telemetry.events import TelemetryEvent

__all__ = ["MAX_VALUE_LEN", "REDACTED", "Sanitizer"]

REDACTED = "***REDACTED***"
MAX_VALUE_LEN = 4096
_TRUNCATED_SUFFIX = "...(truncated)"

# Key names that always cause the value to be dropped.
_SENSITIVE_NAME_RE = re.compile(
    r"(api[_-]?key|secret|token|passwd|password|authorization|"
    r"auth|cookie|private[_-]?key|client[_-]?secret|bearer|credential)",
    re.IGNORECASE,
)

# Value-shaped secrets to scrub even under a non-sensitive key (defense in depth).
_VALUE_SECRET_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{12,}|Bearer\s+\S+|[A-Fa-f0-9]{32,})")


class Sanitizer:
    """Recursively redacts secrets from telemetry payloads."""

    def sanitize_event(self, event: TelemetryEvent) -> TelemetryEvent:
        return TelemetryEvent(
            name=event.name,
            attributes=self.sanitize_mapping(event.attributes),
        )

    def sanitize_mapping(self, mapping: Mapping[str, Any]) -> dict[str, Any]:
        return {str(key): self.sanitize_value(str(key), value) for key, value in mapping.items()}

    def sanitize_value(self, key: str | None, value: Any) -> Any:
        if key is not None and _SENSITIVE_NAME_RE.search(key):
            return REDACTED
        if isinstance(value, SecretStr):
            return REDACTED
        if isinstance(value, BaseException):
            return self.sanitize_exception(value)
        if isinstance(value, Mapping):
            return {str(k): self.sanitize_value(str(k), v) for k, v in value.items()}
        if isinstance(value, str):
            return self._scrub_text(value)
        if isinstance(value, (bytes, bytearray)):
            return self._scrub_text(value.decode("utf-8", errors="replace"))
        if isinstance(value, Sequence):
            return [self.sanitize_value(None, item) for item in value]
        return value

    def sanitize_exception(self, exc: BaseException) -> dict[str, Any]:
        return {
            "type": type(exc).__name__,
            "message": self._scrub_text(str(exc)),
            "args": [self.sanitize_value(None, arg) for arg in exc.args],
        }

    def _scrub_text(self, text: str) -> str:
        scrubbed = _VALUE_SECRET_RE.sub(REDACTED, text)
        if len(scrubbed) > MAX_VALUE_LEN:
            scrubbed = scrubbed[:MAX_VALUE_LEN] + _TRUNCATED_SUFFIX
        return scrubbed
