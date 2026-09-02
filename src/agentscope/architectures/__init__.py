"""AgentScope architectures - contract, identity, registry."""

from agentscope.architectures.base import AgentArchitecture
from agentscope.architectures.errors import (
    ArchitectureError,
    DuplicateArchitectureError,
    UnknownArchitectureError,
)
from agentscope.architectures.identity import ArchitectureIdentity
from agentscope.architectures.registry import ArchitectureFactory, ArchitectureRegistry

__all__ = [
    "AgentArchitecture",
    "ArchitectureError",
    "ArchitectureFactory",
    "ArchitectureIdentity",
    "ArchitectureRegistry",
    "DuplicateArchitectureError",
    "UnknownArchitectureError",
]
