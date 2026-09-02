"""The architecture registry skeleton (design 6).

Resolves a stable ``architecture_key`` to a registered implementation or
factory, and rejects duplicate or unknown keys deterministically. The platform
holds one instance; there is no global singleton.
"""

from __future__ import annotations

from collections.abc import Callable

from agentscope.architectures.base import AgentArchitecture
from agentscope.architectures.errors import (
    DuplicateArchitectureError,
    UnknownArchitectureError,
)

__all__ = ["ArchitectureFactory", "ArchitectureRegistry"]

ArchitectureFactory = Callable[[], AgentArchitecture]


class ArchitectureRegistry:
    """A key -> architecture (or lazy factory) map with deterministic errors."""

    def __init__(self) -> None:
        self._factories: dict[str, ArchitectureFactory] = {}
        self._instances: dict[str, AgentArchitecture] = {}

    def register(self, architecture: AgentArchitecture) -> None:
        """Register a concrete architecture under its own identity key."""
        key = architecture.identity.architecture_key
        self._claim(key)
        self._instances[key] = architecture
        self._factories[key] = lambda: architecture

    def register_factory(self, key: str, factory: ArchitectureFactory) -> None:
        """Register a zero-arg factory that builds an architecture on demand."""
        self._claim(key)
        self._factories[key] = factory

    def resolve(self, key: str) -> AgentArchitecture:
        """Return the architecture for ``key``, building it once if needed."""
        if key not in self._factories:
            raise UnknownArchitectureError(f"no architecture registered for key: {key!r}")
        if key not in self._instances:
            self._instances[key] = self._factories[key]()
        return self._instances[key]

    def keys(self) -> tuple[str, ...]:
        """All registered keys, sorted for deterministic iteration."""
        return tuple(sorted(self._factories))

    def _claim(self, key: str) -> None:
        if key in self._factories:
            raise DuplicateArchitectureError(f"architecture key already registered: {key!r}")

    def __contains__(self, key: object) -> bool:
        return key in self._factories

    def __len__(self) -> int:
        return len(self._factories)
