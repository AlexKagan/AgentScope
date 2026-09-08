"""The LangChain OpenAI-compatible Chat Completions adapter (design D2, step 6).

LangChain owns provider interaction, message conversion, and tool binding. This
adapter owns AgentScope's normalized result, usage, cost, identity, and error
semantics. No LangChain ``AIMessage``, ``usage_metadata``, ``response_metadata``,
or provider exception type escapes this module.

One ``ainvoke`` == exactly one provider attempt. Implicit client retries are
disabled (``max_retries=0``). Retry orchestration belongs above the adapter.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Mapping
from typing import Any

from agentscope.models.configuration import ModelDefinition, ReasoningMode
from agentscope.models.cost import LLMCost, calculate_cost
from agentscope.models.errors import (
    ModelAuthenticationError,
    ModelAuthorizationError,
    ModelConnectionError,
    ModelError,
    ModelInvalidRequestError,
    ModelProviderError,
    ModelRateLimitError,
    ModelResponseNormalizationError,
    ModelTimeoutError,
)
from agentscope.models.identity import SafeModelIdentity
from agentscope.models.requests import ModelRequest, Role, ToolDefinition
from agentscope.models.responses import (
    FinishReason,
    ModelResponse,
    ToolCall,
    ToolCallOrigin,
)
from agentscope.models.usage import normalize_usage

__all__ = ["AuthoritativeCostExtractor", "OpenAICompatibleChatAdapter"]

# A provider-profile hook used only inside this trust boundary: inspect the raw
# response and return an authoritative cost in USD, or ``None``.
AuthoritativeCostExtractor = Callable[[Any], Any | None]

_FINISH_REASONS = {
    "stop": FinishReason.STOP,
    "end_turn": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "max_tokens": FinishReason.LENGTH,
    "tool_calls": FinishReason.TOOL_CALLS,
    "function_call": FinishReason.TOOL_CALLS,
    "content_filter": FinishReason.CONTENT_FILTER,
}
_SAFE_METADATA_KEYS = ("model_name", "finish_reason", "system_fingerprint", "service_tier")


def _openrouter_usage_cost(raw: Any) -> Any | None:
    usage = getattr(raw, "usage_metadata", None)
    if isinstance(usage, Mapping) and "cost" in usage:
        return usage["cost"]
    metadata = _meta(raw)
    for key in ("token_usage", "usage"):
        raw_usage = metadata.get(key)
        if isinstance(raw_usage, Mapping) and "cost" in raw_usage:
            return raw_usage["cost"]
    return None


_AUTHORITATIVE_COST_EXTRACTORS: dict[str, AuthoritativeCostExtractor] = {
    "openrouter_usage": _openrouter_usage_cost,
}


def _tool_schema(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": dict(tool.parameters),
        },
    }


def _portable_init_parameters(definition: ModelDefinition) -> dict[str, Any]:
    supplied = definition.parameters.supplied()
    translated: dict[str, Any] = {}
    for key, value in supplied.items():
        if key == "max_output_tokens":
            translated["max_tokens"] = value
        elif key != "verbosity":
            translated[key] = value
    return translated


def _provider_extra_body(definition: ModelDefinition) -> dict[str, Any]:
    body = dict(definition.provider_options)
    verbosity = definition.parameters.verbosity
    if verbosity is not None:
        body["verbosity"] = verbosity

    reasoning = definition.reasoning
    if reasoning.mode is ReasoningMode.PROVIDER_DEFAULT:
        return body
    if definition.provider == "openrouter":
        if reasoning.mode is ReasoningMode.DISABLED:
            body["reasoning"] = {"effort": "none"}
        else:
            payload: dict[str, Any] = {"exclude": reasoning.exclude}
            if reasoning.effort is not None:
                payload["effort"] = reasoning.effort
            else:
                payload["max_tokens"] = reasoning.max_tokens
            body["reasoning"] = payload
    return body


class OpenAICompatibleChatAdapter:
    """Invokes one OpenAI-compatible chat model through LangChain ``ChatOpenAI``."""

    def __init__(
        self,
        definition: ModelDefinition,
        api_key: str,
        *,
        chat_model_factory: Any = None,
        authoritative_cost_extractor: AuthoritativeCostExtractor | None = None,
    ) -> None:
        self._definition = definition
        self._identity = definition.identity()
        self._cost_extractor = authoritative_cost_extractor
        self._closed = False
        init_kwargs: dict[str, Any] = {
            "model": definition.model_name,
            "base_url": definition.resolved_endpoint,
            "api_key": api_key,
            "timeout": definition.timeout_s,
            "max_retries": 0,
            **_portable_init_parameters(definition),
        }
        extra_body = _provider_extra_body(definition)
        if extra_body:
            init_kwargs["extra_body"] = extra_body
        if chat_model_factory is not None:
            self._model = chat_model_factory(**init_kwargs)
        else:  # pragma: no cover - exercised only by live smokes
            from langchain_openai import ChatOpenAI

            self._model = ChatOpenAI(**init_kwargs)

    @property
    def identity(self) -> SafeModelIdentity:
        return self._identity

    async def ainvoke(self, request: ModelRequest) -> ModelResponse:
        if self._closed:
            raise ModelProviderError("model adapter is closed")
        request.require_capabilities(self._definition)
        try:
            self._definition.validate_invocation_options(request.options)
        except ModelError as exc:
            raise ModelInvalidRequestError(str(exc)) from exc
        messages = _to_langchain_messages(request)

        bound = self._model
        if request.tools:
            kwargs: dict[str, Any] = {}
            if request.tool_choice is not None:
                kwargs["tool_choice"] = request.tool_choice
            bound = self._model.bind_tools([_tool_schema(t) for t in request.tools], **kwargs)

        try:
            raw = await bound.ainvoke(messages, **dict(request.options))
        except asyncio.CancelledError:
            raise  # cancellation is not a provider failure
        except ModelError:
            raise
        except Exception as exc:
            raise self._normalize_error(exc) from exc

        try:
            return self._normalize_response(raw, request)
        except ModelError:
            raise
        except Exception as exc:
            raise ModelResponseNormalizationError("model response could not be normalized") from exc

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        client = getattr(self._model, "root_async_client", None) or getattr(
            self._model, "async_client", None
        )
        close = getattr(client, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

    # -- normalization ----------------------------------------------------

    def _normalize_response(self, raw: Any, request: ModelRequest) -> ModelResponse:
        text = _coerce_text(getattr(raw, "content", None))
        model_call_id = getattr(raw, "id", None) or _meta(raw).get("id")

        if getattr(raw, "invalid_tool_calls", None):
            raise ModelResponseNormalizationError(
                "provider returned tool calls that could not be parsed"
            )

        tool_calls = _normalize_tool_calls(
            getattr(raw, "tool_calls", None) or (), model_call_id or request.call_id
        )
        if text is None and not tool_calls:
            raise ModelResponseNormalizationError(
                "model response contains neither assistant text nor tool calls"
            )

        authoritative = self._extract_authoritative_cost(raw)
        usage = normalize_usage(
            _flatten_usage(getattr(raw, "usage_metadata", None)),
            provider_reported_cost_usd=authoritative,
        )
        metadata = _safe_metadata(_meta(raw))
        cost: LLMCost = calculate_cost(
            usage,
            self._definition.pricing,
            provider_authoritative_cost=usage.provider_reported_cost_usd,
        )

        finish = _meta(raw).get("finish_reason")
        finish_reason = (
            None if finish is None else _FINISH_REASONS.get(finish, FinishReason.UNKNOWN)
        )

        return ModelResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            cost=cost,
            provider_metadata=metadata,
            model_call_id=model_call_id,
        )

    def _extract_authoritative_cost(self, raw: Any) -> Any | None:
        if self._cost_extractor is not None:
            return self._cost_extractor(raw)
        source = self._definition.profile.authoritative_cost_source
        if source is None:
            return None
        return _AUTHORITATIVE_COST_EXTRACTORS[source](raw)

    def _normalize_error(self, exc: BaseException) -> ModelError:
        name = type(exc).__name__
        if isinstance(exc, TimeoutError) or name in {"APITimeoutError", "Timeout"}:
            return ModelTimeoutError("model provider attempt timed out")
        if name == "AuthenticationError":
            return ModelAuthenticationError("model provider rejected the credential")
        if name in {"PermissionDeniedError", "AuthorizationError"}:
            return ModelAuthorizationError("credential is not permitted for this model or action")
        if name == "RateLimitError":
            return ModelRateLimitError("model provider rate-limited the request")
        if name in {"APIConnectionError", "APIConnectionTimeoutError"}:
            return ModelConnectionError("could not reach the model provider endpoint")
        if name in {
            "BadRequestError",
            "NotFoundError",
            "UnprocessableEntityError",
            "ConflictError",
        }:
            return ModelInvalidRequestError("model provider rejected the request payload")
        status = getattr(exc, "status_code", None)
        if isinstance(status, int):
            if status == 401:
                return ModelAuthenticationError("model provider rejected the credential")
            if status == 403:
                return ModelAuthorizationError(
                    "credential is not permitted for this model or action"
                )
            if status == 408:
                return ModelTimeoutError("model provider attempt timed out")
            if status == 429:
                return ModelRateLimitError("model provider rate-limited the request")
            if 400 <= status < 500:
                return ModelInvalidRequestError("model provider rejected the request payload")
        return ModelProviderError("model provider returned an unclassified failure")


def _meta(raw: Any) -> Mapping[str, Any]:
    meta = getattr(raw, "response_metadata", None)
    return meta if isinstance(meta, Mapping) else {}


def _coerce_text(content: Any) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        return content or None
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, Mapping) and block.get("type") == "text"
        ]
        joined = "".join(parts)
        return joined or None
    return None


def _normalize_tool_calls(raw_calls: Any, seed: str) -> tuple[ToolCall, ...]:
    calls: list[ToolCall] = []
    for index, call in enumerate(raw_calls):
        name = call.get("name") if isinstance(call, Mapping) else getattr(call, "name", None)
        args = call.get("args") if isinstance(call, Mapping) else getattr(call, "args", None)
        call_id = call.get("id") if isinstance(call, Mapping) else getattr(call, "id", None)
        if not name:
            raise ModelResponseNormalizationError("provider tool call has no name")
        if not isinstance(args, Mapping):
            raise ModelResponseNormalizationError(
                f"tool call {name!r} arguments are not a JSON object"
            )
        origin = ToolCallOrigin.PROVIDER
        if not call_id:
            call_id = f"{seed}-{index}"
            origin = ToolCallOrigin.GENERATED
        calls.append(ToolCall(id=call_id, name=name, arguments=dict(args), origin=origin))
    return tuple(calls)


def _flatten_usage(usage_metadata: Any) -> Mapping[str, Any] | None:
    if not isinstance(usage_metadata, Mapping):
        return None  # normalize_usage will raise the normalization error
    flat: dict[str, Any] = dict(usage_metadata)
    input_details = usage_metadata.get("input_token_details")
    if isinstance(input_details, Mapping) and "cache_read" in input_details:
        flat.setdefault("cached_input_tokens", input_details["cache_read"])
    output_details = usage_metadata.get("output_token_details")
    if isinstance(output_details, Mapping) and "reasoning" in output_details:
        flat.setdefault("reasoning_tokens", output_details["reasoning"])
    return flat


def _safe_metadata(meta: Mapping[str, Any]) -> dict[str, Any]:
    return {key: meta[key] for key in _SAFE_METADATA_KEYS if isinstance(meta.get(key), (str, int))}


def _to_langchain_messages(request: ModelRequest) -> list[Any]:
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )

    out: list[Any] = []
    for message in request.messages:
        if message.role is Role.SYSTEM:
            out.append(SystemMessage(content=message.content))
        elif message.role is Role.USER:
            out.append(HumanMessage(content=message.content))
        elif message.role is Role.ASSISTANT:
            out.append(
                AIMessage(
                    content=message.content,
                    tool_calls=[
                        {
                            "name": call.name,
                            "args": dict(call.arguments),
                            "id": call.id,
                            "type": "tool_call",
                        }
                        for call in message.tool_calls
                    ],
                )
            )
        else:  # Role.TOOL
            out.append(
                ToolMessage(content=message.content, tool_call_id=message.tool_call_id or "")
            )
    return out
