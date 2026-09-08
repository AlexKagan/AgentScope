"""Normalized model response and structured tool calls (design 7.3).

The raw provider/LangChain response is never retained here or in durable state.
Every tool call is structured: a call ID, a tool name, and a JSON-compatible
argument mapping. Malformed arguments or an unrecoverable missing ID are
normalization failures, not free-form text actions.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentscope.models.cost import LLMCost
from agentscope.models.usage import LLMUsage

__all__ = ["FinishReason", "ModelResponse", "ToolCall", "ToolCallOrigin"]


class FinishReason(StrEnum):
    """Normalized reason a generation stopped."""

    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"
    UNKNOWN = "unknown"


class ToolCallOrigin(StrEnum):
    """Whether a tool-call ID came from the provider or was generated locally."""

    PROVIDER = "provider"
    GENERATED = "generated"


class ToolCall(BaseModel):
    """One structured tool call requested by the model."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: Mapping[str, Any]
    origin: ToolCallOrigin = ToolCallOrigin.PROVIDER


class ModelResponse(BaseModel):
    """A frozen, provider-neutral normalization of one model call."""

    model_config = ConfigDict(frozen=True)

    text: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: FinishReason | None = None
    usage: LLMUsage
    cost: LLMCost
    provider_metadata: Mapping[str, Any] = Field(default_factory=dict)
    model_call_id: str | None = None
