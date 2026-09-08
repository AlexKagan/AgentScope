"""Trusted model-adapter construction (design 8.3, D4).

This is the seam where a raw credential becomes a narrow authenticated
capability: a :class:`~agentscope.models.protocol.ModelAdapter`. Construction is
local and eager (no network); the first provider I/O happens on ``ainvoke``.
Only :mod:`agentscope.bootstrap` calls this. The LangChain import is lazy so a
model-free runtime configuration never loads a provider package.
"""

from __future__ import annotations

from typing import Protocol

from agentscope.models.configuration import ModelDefinition
from agentscope.models.protocol import ModelAdapter

__all__ = ["ModelAdapterFactory", "default_model_adapter_factory"]


class ModelAdapterFactory(Protocol):
    """Builds a live model adapter from a definition and its resolved credential."""

    def __call__(self, definition: ModelDefinition, api_key: str) -> ModelAdapter: ...


def default_model_adapter_factory(definition: ModelDefinition, api_key: str) -> ModelAdapter:
    """Construct the generic OpenAI-compatible LangChain adapter."""
    from agentscope.models.openai_compatible import OpenAICompatibleChatAdapter

    return OpenAICompatibleChatAdapter(definition, api_key)
