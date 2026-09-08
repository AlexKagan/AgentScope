"""Stable-key model registration and resolution (design 8.1, D3).

The registry maps a stable, user-facing configuration key (``primary-reasoner``)
to its canonical :class:`ModelDefinition` and the live
:class:`~agentscope.models.protocol.ModelAdapter` built for it at composition.
Only the key and the safe identity may enter durable state; the adapter and its
authenticated client stay runtime dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentscope.models.configuration import ModelDefinition
from agentscope.models.errors import ModelConfigurationError
from agentscope.models.protocol import ModelAdapter

__all__ = ["ModelRegistry", "ResolvedModel"]


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    """A stable key resolved to its definition and its live adapter."""

    definition: ModelDefinition
    adapter: ModelAdapter


class ModelRegistry:
    """A stable-key -> (definition, adapter) map with deterministic errors."""

    def __init__(self) -> None:
        self._entries: dict[str, ResolvedModel] = {}

    def register(self, definition: ModelDefinition, adapter: ModelAdapter) -> None:
        """Register ``adapter`` under ``definition.key``.

        Raises:
            ModelConfigurationError: the key is already registered, or the
                adapter's identity does not match the definition's.
        """
        key = definition.key
        if key in self._entries:
            raise ModelConfigurationError(f"model key already registered: {key!r}")
        if adapter.identity != definition.identity():
            raise ModelConfigurationError(f"adapter identity does not match definition {key!r}")
        self._entries[key] = ResolvedModel(definition=definition, adapter=adapter)

    def resolve(self, key: str) -> ResolvedModel:
        """Return the :class:`ResolvedModel` for ``key`` or raise."""
        try:
            return self._entries[key]
        except KeyError:
            raise ModelConfigurationError(f"no model registered for key: {key!r}") from None

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def __contains__(self, key: object) -> bool:
        return key in self._entries

    def __len__(self) -> int:
        return len(self._entries)
