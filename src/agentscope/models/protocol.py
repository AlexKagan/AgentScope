"""The async AgentScope model protocol (design 7, D6).

The public model operation is :meth:`ModelAdapter.ainvoke`. Network I/O is
asynchronous; a synchronous wrapper is not added until a concrete caller needs
one. Implementations translate provider results into the normalized
:class:`~agentscope.models.responses.ModelResponse` and never leak LangChain or
provider types.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agentscope.models.identity import SafeModelIdentity
from agentscope.models.requests import ModelRequest
from agentscope.models.responses import ModelResponse

__all__ = ["ModelAdapter"]


@runtime_checkable
class ModelAdapter(Protocol):
    """A live, non-serializable capability that invokes one configured model."""

    @property
    def identity(self) -> SafeModelIdentity:
        """The credential-free identity of the model this adapter serves."""
        ...

    async def ainvoke(self, request: ModelRequest) -> ModelResponse:
        """Perform exactly one provider attempt and return a normalized response.

        Raises a subclass of :class:`~agentscope.models.errors.ModelError` for
        every provider or normalization failure; never retries.
        """
        ...

    async def aclose(self) -> None:
        """Release any provider connection resources. Must be idempotent."""
        ...
