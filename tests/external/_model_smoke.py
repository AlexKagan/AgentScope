"""Shared two-call live-model contract for the provider smokes (design 11.4).

Call 1 (plain): ask for a fixed short token; assert non-empty normalized text and
no tool calls. Call 2 (structured): bind a harmless synthetic
``lookup_temperature(city)`` schema and force it; assert the returned call name,
JSON-object arguments, an ID, normalized usage, and a cost-source value. The tool
is never executed. Assertions tolerate natural-language variation and
provider-generated IDs; they never assert exact token counts or cost amounts.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from agentscope.models.configuration import ModelDefinition
from agentscope.models.cost import CostSource
from agentscope.models.openai_compatible import OpenAICompatibleChatAdapter
from agentscope.models.requests import Message, ModelRequest, Role, ToolDefinition

_LOOKUP_TEMPERATURE = ToolDefinition(
    name="lookup_temperature",
    description="Return the current temperature for a city.",
    parameters={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
)


@dataclass(frozen=True)
class SmokeResult:
    adapter_versions: dict[str, str]


def _adapter(definition: ModelDefinition, api_key: str) -> OpenAICompatibleChatAdapter:
    return OpenAICompatibleChatAdapter(definition, api_key)


def run_model_smoke(definition: ModelDefinition, api_key: str) -> None:
    adapter = _adapter(definition, api_key)
    try:
        asyncio.run(_plain(adapter))
        asyncio.run(_structured(adapter))
    finally:
        asyncio.run(adapter.aclose())


async def _plain(adapter: OpenAICompatibleChatAdapter) -> None:
    request = ModelRequest(
        messages=(
            Message(role=Role.SYSTEM, content="Reply with exactly the word READY."),
            Message(role=Role.USER, content="Are you there?"),
        )
    )
    response = await adapter.ainvoke(request)
    assert response.text is not None and response.text.strip() != ""
    assert response.tool_calls == ()
    assert response.usage.input_tokens >= 0
    assert response.usage.output_tokens >= 0


async def _structured(adapter: OpenAICompatibleChatAdapter) -> None:
    request = ModelRequest(
        messages=(Message(role=Role.USER, content="What is the temperature in Paris right now?"),),
        tools=(_LOOKUP_TEMPERATURE,),
        tool_choice="lookup_temperature",
    )
    response = await adapter.ainvoke(request)
    assert len(response.tool_calls) >= 1
    call = response.tool_calls[0]
    assert call.name == "lookup_temperature"
    assert isinstance(call.arguments, dict)
    assert call.id
    assert response.usage.total_tokens >= 1
    assert response.cost.source in {
        CostSource.PROVIDER_REPORTED,
        CostSource.CONFIGURED_PRICING,
        CostSource.UNKNOWN,
    }
