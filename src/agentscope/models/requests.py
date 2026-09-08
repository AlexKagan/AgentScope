"""Validated model request and tool-schema inputs (design 7.2).

Validation happens at the AgentScope boundary. The adapter may use LangChain
message and tool-schema facilities internally, but a :class:`ModelRequest` that
reaches an adapter has already been checked: supported roles and non-empty
content, unique tool names, JSON-Schema-shaped (non-callable) tool parameters,
and no per-call model/provider/endpoint/credential/pricing overrides.

Phase 1A.2 does not accept callable tools: the model layer *describes* tools; it
never executes them.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentscope.models.configuration import Capability, ModelDefinition
from agentscope.models.errors import ModelCapabilityError, ModelInvalidRequestError

__all__ = ["Message", "ModelRequest", "Role", "ToolDefinition"]

_TOOL_CHOICE_MODES = frozenset({"auto", "required", "none"})
_FORBIDDEN_OPTION_KEYS = frozenset(
    {
        "model",
        "model_name",
        "provider",
        "protocol",
        "endpoint",
        "base_url",
        "credential",
        "credential_ref",
        "api_key",
        "pricing",
    }
)


class Role(StrEnum):
    """Supported conversation roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """One normalized conversation message."""

    model_config = ConfigDict(frozen=True)

    role: Role
    content: str
    tool_call_id: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> Message:
        if self.content == "" or self.content.strip() == "":
            raise ModelInvalidRequestError(f"message content for role {self.role} is empty")
        if self.role is Role.TOOL and not self.tool_call_id:
            raise ModelInvalidRequestError("a tool-role message requires a tool_call_id")
        return self


class ToolDefinition(BaseModel):
    """A declared tool: a name, a description, and a JSON-Schema object."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=r"^[a-zA-Z_][a-zA-Z0-9_-]*$")
    description: str = ""
    parameters: Mapping[str, Any]

    @model_validator(mode="after")
    def _validate_schema(self) -> ToolDefinition:
        params = self.parameters
        if callable(params):  # pragma: no cover - defensive
            raise ModelInvalidRequestError(f"tool {self.name!r} parameters must not be callable")
        try:
            json.dumps(params)
        except TypeError as exc:
            raise ModelInvalidRequestError(
                f"tool {self.name!r} parameters are not a valid JSON Schema "
                "(non-serializable or callable value)"
            ) from exc
        if params.get("type") != "object":
            raise ModelInvalidRequestError(
                f'tool {self.name!r} parameters must be a JSON Schema object ("type": "object")'
            )
        return self


class ModelRequest(BaseModel):
    """A frozen, validated request handed to a :class:`ModelAdapter`."""

    model_config = ConfigDict(frozen=True)

    messages: tuple[Message, ...] = Field(min_length=1)
    tools: tuple[ToolDefinition, ...] = ()
    tool_choice: str | None = None
    call_id: str = Field(default_factory=lambda: uuid4().hex)
    options: Mapping[str, str | int | float | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> ModelRequest:
        names = [t.name for t in self.tools]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ModelInvalidRequestError(f"duplicate tool names: {dupes}")

        if self.tool_choice is not None:
            if not self.tools:
                raise ModelInvalidRequestError("tool_choice was set but no tools were provided")
            if self.tool_choice not in _TOOL_CHOICE_MODES and self.tool_choice not in names:
                raise ModelInvalidRequestError(
                    f"tool_choice {self.tool_choice!r} is neither a mode "
                    f"{sorted(_TOOL_CHOICE_MODES)} nor a declared tool name"
                )

        forbidden = sorted(set(self.options) & _FORBIDDEN_OPTION_KEYS)
        if forbidden:
            raise ModelInvalidRequestError(
                f"per-call options may not override {forbidden}; these are fixed by the "
                "model definition"
            )
        return self

    def require_capabilities(self, definition: ModelDefinition) -> None:
        """Raise :class:`ModelCapabilityError` if the definition can't serve this request.

        Called by the adapter before any provider I/O.
        """
        wants_tools = bool(self.tools) or (
            self.tool_choice is not None and self.tool_choice != "none"
        )
        if wants_tools and not definition.supports(Capability.TOOL_CALLING):
            raise ModelCapabilityError(
                f"request needs tool calling but model {definition.key!r} does not declare it"
            )
