"""Reusable model-adapter contract (design 11.3).

Run here against a deterministic scripted LangChain chat model. The same
behavioral assertions are intended to be reusable against live OpenRouter and
Meta-compatible profiles (``tests/external/``); provider-neutral assertions live
here, provider-specific findings stay with the provider.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from agentscope.models.configuration import ModelDefinition
from agentscope.models.cost import CostSource, PriceCard
from agentscope.models.errors import (
    ModelError,
    ModelProviderError,
    ModelRateLimitError,
    ModelResponseNormalizationError,
    ModelTimeoutError,
)
from agentscope.models.openai_compatible import OpenAICompatibleChatAdapter
from agentscope.models.requests import Message, ModelRequest, Role, ToolDefinition
from agentscope.models.responses import ToolCallOrigin
from tests.contract._scripted_model import (
    ScriptedChatModel,
    ScriptedMessage,
    named_error,
    slow_then_cancelled,
    usage,
)

_PRICING = PriceCard(
    pricing_id="scripted",
    version="v1",
    input_usd_per_mtok=Decimal("1.000000"),
    output_usd_per_mtok=Decimal("2.000000"),
)


def _defn(**over: Any) -> ModelDefinition:
    base: dict[str, Any] = {
        "key": "scripted",
        "provider": "openrouter",
        "model_name": "scripted/model",
        "credential_ref": "openrouter_api_key",
    }
    base.update(over)
    return ModelDefinition(**base)


def _adapter(
    *script: Any,
    pricing: PriceCard | None = None,
    cost_extractor: Callable[[Any], Any] | None = None,
) -> tuple[OpenAICompatibleChatAdapter, ScriptedChatModel]:
    model = ScriptedChatModel(*script)
    adapter = OpenAICompatibleChatAdapter(
        _defn(pricing=pricing),
        "fake-key",
        chat_model_factory=lambda: model,
        authoritative_cost_extractor=cost_extractor,
    )
    return adapter, model


def _text_request(prompt: str = "hello") -> ModelRequest:
    return ModelRequest(messages=(Message(role=Role.USER, content=prompt),))


def _tool_request() -> ModelRequest:
    tool = ToolDefinition(
        name="lookup_temperature",
        description="look up a city temperature",
        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
    )
    return ModelRequest(
        messages=(Message(role=Role.USER, content="temp?"),),
        tools=(tool,),
        tool_choice="lookup_temperature",
    )


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# -- text ---------------------------------------------------------------------


def test_plain_text() -> None:
    adapter, _ = _adapter(ScriptedMessage(content="Hello there", usage_metadata=usage()))
    resp = run(adapter.ainvoke(_text_request()))
    assert resp.text == "Hello there"
    assert resp.tool_calls == ()


def test_one_forced_tool_call() -> None:
    msg = ScriptedMessage(
        content="",
        tool_calls=[{"name": "lookup_temperature", "args": {"city": "Paris"}, "id": "call_a"}],
        usage_metadata=usage(),
        response_metadata={"finish_reason": "tool_calls"},
    )
    adapter, model = _adapter(msg)
    resp = run(adapter.ainvoke(_tool_request()))
    assert resp.text is None
    assert len(resp.tool_calls) == 1
    call = resp.tool_calls[0]
    assert (call.name, call.id, call.arguments, call.origin) == (
        "lookup_temperature",
        "call_a",
        {"city": "Paris"},
        ToolCallOrigin.PROVIDER,
    )
    assert model.bound_kwargs == {"tool_choice": "lookup_temperature"}


def test_multiple_tool_calls_keep_provider_order() -> None:
    msg = ScriptedMessage(
        tool_calls=[
            {"name": "a", "args": {"n": 1}, "id": "c1"},
            {"name": "b", "args": {"n": 2}, "id": "c2"},
            {"name": "a", "args": {"n": 3}, "id": "c3"},
        ],
        usage_metadata=usage(),
    )
    adapter, _ = _adapter(msg)
    resp = run(adapter.ainvoke(_tool_request()))
    assert [c.id for c in resp.tool_calls] == ["c1", "c2", "c3"]
    assert [c.name for c in resp.tool_calls] == ["a", "b", "a"]


def test_text_plus_tool_call_both_retained() -> None:
    msg = ScriptedMessage(
        content="calling a tool",
        tool_calls=[{"name": "a", "args": {}, "id": "c1"}],
        usage_metadata=usage(),
    )
    adapter, _ = _adapter(msg)
    resp = run(adapter.ainvoke(_tool_request()))
    assert resp.text == "calling a tool"
    assert len(resp.tool_calls) == 1


def test_unknown_returned_tool_is_preserved() -> None:
    msg = ScriptedMessage(
        tool_calls=[{"name": "not_declared", "args": {}, "id": "c1"}], usage_metadata=usage()
    )
    adapter, _ = _adapter(msg)
    resp = run(adapter.ainvoke(_tool_request()))
    assert resp.tool_calls[0].name == "not_declared"


def test_malformed_tool_arguments_raise_normalization_error() -> None:
    msg = ScriptedMessage(
        tool_calls=[{"name": "a", "args": "not-a-dict", "id": "c1"}], usage_metadata=usage()
    )
    adapter, _ = _adapter(msg)
    with pytest.raises(ModelResponseNormalizationError):
        run(adapter.ainvoke(_tool_request()))


def test_invalid_tool_calls_raise_normalization_error() -> None:
    msg = ScriptedMessage(
        invalid_tool_calls=[{"name": "a", "args": "{bad json", "id": "c1"}],
        usage_metadata=usage(),
    )
    adapter, _ = _adapter(msg)
    with pytest.raises(ModelResponseNormalizationError):
        run(adapter.ainvoke(_tool_request()))


def test_missing_provider_call_id_is_generated_with_origin_flag() -> None:
    msg = ScriptedMessage(
        tool_calls=[{"name": "a", "args": {}, "id": None}],
        usage_metadata=usage(),
        id="run-xyz",
    )
    adapter, _ = _adapter(msg)
    resp = run(adapter.ainvoke(_tool_request()))
    assert resp.tool_calls[0].origin is ToolCallOrigin.GENERATED
    assert resp.tool_calls[0].id == "run-xyz-0"


# -- usage ------------------------------------------------------------------


def test_standard_usage_is_normalized() -> None:
    adapter, _ = _adapter(ScriptedMessage(content="ok", usage_metadata=usage(10, 5)))
    resp = run(adapter.ainvoke(_text_request()))
    assert (resp.usage.input_tokens, resp.usage.output_tokens, resp.usage.total_tokens) == (
        10,
        5,
        15,
    )


def test_cached_and_reasoning_usage_dimensions_are_normalized() -> None:
    meta = usage(
        100,
        40,
        input_token_details={"cache_read": 30},
        output_token_details={"reasoning": 12},
    )
    adapter, _ = _adapter(ScriptedMessage(content="ok", usage_metadata=meta))
    resp = run(adapter.ainvoke(_text_request()))
    assert resp.usage.cached_input_tokens == 30
    assert resp.usage.reasoning_tokens == 12


def test_missing_usage_is_normalization_error() -> None:
    adapter, _ = _adapter(ScriptedMessage(content="ok", usage_metadata=None))
    with pytest.raises(ModelResponseNormalizationError):
        run(adapter.ainvoke(_text_request()))


# -- cost -----------------------------------------------------------------------


def test_authoritative_provider_cost_wins() -> None:
    adapter, _ = _adapter(
        ScriptedMessage(content="ok", usage_metadata=usage(1000, 500)),
        pricing=_PRICING,
        cost_extractor=lambda _meta: Decimal("0.99"),
    )
    resp = run(adapter.ainvoke(_text_request()))
    assert resp.cost.source is CostSource.PROVIDER_REPORTED
    assert resp.cost.amount_usd == Decimal("0.99")


def test_configured_pricing_is_exact() -> None:
    adapter, _ = _adapter(
        ScriptedMessage(content="ok", usage_metadata=usage(1000, 500)), pricing=_PRICING
    )
    resp = run(adapter.ainvoke(_text_request()))
    assert resp.cost.source is CostSource.CONFIGURED_PRICING
    assert resp.cost.amount_usd == Decimal("0.002")
    assert resp.cost.pricing_identity == "scripted#unknown"


def test_no_cost_data_is_explicit_unknown() -> None:
    adapter, _ = _adapter(ScriptedMessage(content="ok", usage_metadata=usage()))
    resp = run(adapter.ainvoke(_text_request()))
    assert resp.cost.source is CostSource.UNKNOWN
    assert resp.cost.amount_usd is None


# -- errors -------------------------------------------------------------------


def test_provider_exception_maps_to_stable_category_with_chained_cause() -> None:
    original = named_error("RateLimitError", "slow down")
    adapter, _ = _adapter(original)
    with pytest.raises(ModelRateLimitError) as excinfo:
        run(adapter.ainvoke(_text_request()))
    assert excinfo.value.__cause__ is original


def test_unclassified_provider_failure_maps_to_provider_error() -> None:
    adapter, _ = _adapter(named_error("WeirdError", "???"))
    with pytest.raises(ModelProviderError):
        run(adapter.ainvoke(_text_request()))


def test_timeout_is_normalized_and_only_one_attempt() -> None:
    adapter, model = _adapter(TimeoutError("timed out"))
    with pytest.raises(ModelTimeoutError):
        run(adapter.ainvoke(_text_request()))
    assert model.calls == 1


def test_concurrent_invocations_do_not_leak_state() -> None:
    async def echo(messages: list[Any]) -> ScriptedMessage:
        last = messages[-1].content
        await asyncio.sleep(0)
        return ScriptedMessage(content=f"echo:{last}", usage_metadata=usage())

    adapter, _ = _adapter(echo)

    async def drive() -> list[str]:
        results = await asyncio.gather(
            adapter.ainvoke(_text_request("alpha")),
            adapter.ainvoke(_text_request("beta")),
        )
        return [r.text or "" for r in results]

    assert set(run(drive())) == {"echo:alpha", "echo:beta"}


def test_cancellation_propagates_and_is_not_rewritten() -> None:
    adapter, _ = _adapter(slow_then_cancelled)

    async def drive() -> None:
        task = asyncio.ensure_future(adapter.ainvoke(_text_request()))
        await asyncio.sleep(0.01)
        task.cancel()
        await task

    with pytest.raises(asyncio.CancelledError):
        run(drive())


def test_cancellation_error_is_not_a_model_error() -> None:
    assert not issubclass(asyncio.CancelledError, ModelError)
