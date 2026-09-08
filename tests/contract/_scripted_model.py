"""A deterministic stand-in for a LangChain chat model.

Only the LangChain/provider boundary is scripted. AgentScope normalization is
never mocked. Message shapes mirror ``AIMessage`` / ``usage_metadata`` /
``response_metadata`` closely enough to exercise the real mapping code.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScriptedMessage:
    """A minimal ``AIMessage``-like object."""

    content: str | list[Any] = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    invalid_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage_metadata: dict[str, Any] | None = None
    response_metadata: dict[str, Any] = field(default_factory=dict)
    id: str | None = None


Script = ScriptedMessage | BaseException | Callable[[list[Any]], Awaitable[Any]]


class ScriptedChatModel:
    """Returns queued scripted results; raises queued exceptions; awaits callables."""

    def __init__(self, *script: Script) -> None:
        self._script: list[Script] = list(script)
        self.calls = 0
        self.bound_tools: list[dict[str, Any]] | None = None
        self.bound_kwargs: dict[str, Any] | None = None
        self.invoke_kwargs: list[dict[str, Any]] = []
        self.received: list[list[Any]] = []
        self.root_async_client: Any = None
        self.async_client: Any = None

    def bind_tools(self, tools: list[dict[str, Any]], **kwargs: Any) -> ScriptedChatModel:
        self.bound_tools = tools
        self.bound_kwargs = kwargs
        return self

    async def ainvoke(self, messages: list[Any], **kwargs: Any) -> Any:
        self.calls += 1
        self.received.append(messages)
        self.invoke_kwargs.append(kwargs)
        item = self._script.pop(0) if len(self._script) > 1 else self._script[0]
        if isinstance(item, BaseException):
            raise item
        if callable(item):
            return await item(messages)
        return item


def usage(input_tokens: int = 8, output_tokens: int = 4, **extra: Any) -> dict[str, Any]:
    """A standard ``usage_metadata`` mapping."""
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        **extra,
    }


def named_error(name: str, message: str = "boom", **attrs: Any) -> Exception:
    """Build an exception whose class name drives the adapter's error mapping."""
    exc: Exception = type(name, (Exception,), {})(message)
    for key, value in attrs.items():
        setattr(exc, key, value)
    return exc


async def slow_then_cancelled(_messages: list[Any]) -> Any:  # pragma: no cover - timing
    await asyncio.sleep(3600)
