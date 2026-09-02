"""Stable architecture identity fields (design 7).

These conventions exist in Phase 0 so that later reproducible evaluation
(Phase 1B) can distinguish architecture changes from model, prompt,
tool-schema, runtime, and policy changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["ArchitectureIdentity"]

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(frozen=True, slots=True)
class ArchitectureIdentity:
    """Human-readable registry identity plus an explicit behavior version."""

    architecture_key: str
    architecture_version: str

    def __post_init__(self) -> None:
        if not _KEY_RE.match(self.architecture_key):
            raise ValueError(
                f"architecture_key must match ^[a-z][a-z0-9_]*$, got {self.architecture_key!r}"
            )
        if not _VERSION_RE.match(self.architecture_version):
            raise ValueError(
                "architecture_version must be 'MAJOR.MINOR.PATCH', "
                f"got {self.architecture_version!r}"
            )
