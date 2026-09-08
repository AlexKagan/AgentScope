"""Request and tool-schema validation at the AgentScope boundary (design 7.2)."""

from __future__ import annotations

import pytest

from agentscope.models.configuration import Capability, ModelDefinition
from agentscope.models.errors import ModelCapabilityError, ModelInvalidRequestError
from agentscope.models.requests import Message, ModelRequest, Role, ToolDefinition
from agentscope.models.responses import ToolCall

_OBJ_SCHEMA = {"type": "object", "properties": {"city": {"type": "string"}}}


def _msg(text: str = "hello", role: Role = Role.USER) -> Message:
    return Message(role=role, content=text)


def _tool(name: str = "lookup_temperature") -> ToolDefinition:
    return ToolDefinition(name=name, description="d", parameters=_OBJ_SCHEMA)


def _defn(
    caps: tuple[Capability, ...] = (Capability.TEXT, Capability.TOOL_CALLING),
) -> ModelDefinition:
    return ModelDefinition(
        key="k",
        provider="meta",
        model_name="muse-spark-1.3",
        credential_ref="meta_model_api_key",
        capabilities=caps,
    )


def test_text_messages_in_supported_roles() -> None:
    req = ModelRequest(
        messages=(
            Message(role=Role.SYSTEM, content="be brief"),
            Message(role=Role.USER, content="hi"),
        )
    )
    assert len(req.messages) == 2
    assert req.call_id  # auto-generated


@pytest.mark.parametrize("bad", ["", "   "])
def test_empty_message_content_is_rejected(bad: str) -> None:
    with pytest.raises(ModelInvalidRequestError):
        _msg(bad)


def test_tool_role_requires_tool_call_id() -> None:
    with pytest.raises(ModelInvalidRequestError):
        Message(role=Role.TOOL, content="result")
    Message(role=Role.TOOL, content="result", tool_call_id="call_1")


def test_valid_object_schema_accepted() -> None:
    assert _tool().parameters["type"] == "object"


def test_non_object_schema_rejected() -> None:
    with pytest.raises(ModelInvalidRequestError):
        ToolDefinition(name="t", parameters={"type": "string"})


def test_structurally_invalid_json_schema_rejected() -> None:
    with pytest.raises(ModelInvalidRequestError):
        ToolDefinition(name="t", parameters={"type": "object", "properties": 7})


def test_callable_in_schema_rejected() -> None:
    with pytest.raises(ModelInvalidRequestError):
        ToolDefinition(name="t", parameters={"type": "object", "fn": lambda: None})


def test_duplicate_tool_names_rejected() -> None:
    with pytest.raises(ModelInvalidRequestError):
        ModelRequest(messages=(_msg(),), tools=(_tool("a"), _tool("a")))


def test_tool_choice_without_tools_rejected() -> None:
    with pytest.raises(ModelInvalidRequestError):
        ModelRequest(messages=(_msg(),), tool_choice="required")


def test_tool_choice_unknown_name_rejected() -> None:
    with pytest.raises(ModelInvalidRequestError):
        ModelRequest(messages=(_msg(),), tools=(_tool("a"),), tool_choice="b")


def test_tool_choice_mode_and_name_accepted() -> None:
    ModelRequest(messages=(_msg(),), tools=(_tool("a"),), tool_choice="required")
    ModelRequest(messages=(_msg(),), tools=(_tool("a"),), tool_choice="a")


@pytest.mark.parametrize(
    "key", ["model", "provider", "base_url", "credential_ref", "api_key", "pricing"]
)
def test_per_call_override_of_identity_is_rejected(key: str) -> None:
    with pytest.raises(ModelInvalidRequestError):
        ModelRequest(messages=(_msg(),), options={key: "x"})


def test_safe_per_call_option_is_accepted() -> None:
    req = ModelRequest(messages=(_msg(),), options={"temperature": 0.0})
    assert req.options["temperature"] == 0.0


def test_capability_check_rejects_tools_when_not_declared() -> None:
    req = ModelRequest(messages=(_msg(),), tools=(_tool(),))
    with pytest.raises(ModelCapabilityError):
        req.require_capabilities(_defn(caps=(Capability.TEXT,)))
    req.require_capabilities(_defn())  # tool_calling declared -> ok


def test_request_is_frozen() -> None:
    req = ModelRequest(messages=(_msg(),))
    with pytest.raises(Exception):  # noqa: B017
        req.tool_choice = "required"  # type: ignore[misc]


def test_request_and_tool_schema_are_deeply_immutable() -> None:
    schema = {"type": "object", "properties": {"city": {"type": "string"}}}
    tool = ToolDefinition(name="t", parameters=schema)
    schema["properties"] = {}
    assert "city" in tool.parameters["properties"]
    with pytest.raises(TypeError):
        tool.parameters["properties"]["city"] = {}  # type: ignore[index]

    req = ModelRequest(messages=(_msg(),), options={"temperature": 0.1})
    with pytest.raises(TypeError):
        req.options["temperature"] = 0.2  # type: ignore[index]


def test_tool_call_arguments_must_be_json_compatible() -> None:
    with pytest.raises(Exception, match="JSON-compatible"):
        ToolCall(id="call_1", name="t", arguments={"bad": object()})
