"""Deterministic errors raised by the architecture registry."""

from __future__ import annotations

__all__ = [
    "ArchitectureError",
    "DuplicateArchitectureError",
    "UnknownArchitectureError",
]


class ArchitectureError(Exception):
    """Base class for architecture-registry errors."""


class DuplicateArchitectureError(ArchitectureError):
    """Raised when an architecture key is registered more than once."""


class UnknownArchitectureError(ArchitectureError):
    """Raised when an architecture key is not present in the registry."""
