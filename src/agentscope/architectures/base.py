"""The minimal architecture contract (design 6, 7).

Phase 0 defines only *identity*. It deliberately exposes no ``build`` or ``run``
surface: agent topology is an experimental variable and each architecture owns
its own control flow, state, and scheduling. Later phases add execution seams.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agentscope.architectures.identity import ArchitectureIdentity

__all__ = ["AgentArchitecture"]


@runtime_checkable
class AgentArchitecture(Protocol):
    """An experimental agent topology registered with the platform."""

    @property
    def identity(self) -> ArchitectureIdentity:
        """Stable registry key plus explicit behavior version."""
        ...

    def describe(self) -> str:
        """A short human-readable summary of this architecture."""
        ...
