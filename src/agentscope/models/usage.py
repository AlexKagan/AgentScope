"""Normalized token usage (design 7.4).

``LLMUsage`` is the single representation of token accounting in AgentScope. No
downstream component reads LangChain ``usage_metadata`` or a provider response
dictionary; extraction happens once, here, inside :func:`normalize_usage`.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentscope.models.errors import ModelResponseNormalizationError

__all__ = ["LLMUsage", "normalize_usage"]

_INPUT_KEYS = ("input_tokens", "prompt_tokens")
_OUTPUT_KEYS = ("output_tokens", "completion_tokens")
_TOTAL_KEYS = ("total_tokens",)
_CACHED_KEYS = ("cached_input_tokens", "cache_read_input_tokens")
_REASONING_KEYS = ("reasoning_tokens",)


class LLMUsage(BaseModel):
    """Non-negative, integral token accounting for one successful model call."""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    provider_reported_cost_usd: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    total_discrepancy: bool = False


def _first_present(raw: Mapping[str, Any], keys: tuple[str, ...]) -> tuple[bool, Any]:
    for key in keys:
        if key in raw:
            return True, raw[key]
    return False, None


def _token_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ModelResponseNormalizationError(f"usage field {field!r} is a boolean, not a count")
    if not isinstance(value, int):
        raise ModelResponseNormalizationError(
            f"usage field {field!r} must be a non-negative integer, got {type(value).__name__}"
        )
    if value < 0:
        raise ModelResponseNormalizationError(f"usage field {field!r} is negative: {value}")
    return value


def _cost(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:  # pragma: no cover - defensive
        raise ModelResponseNormalizationError("provider-reported cost is not a number") from exc
    if not result.is_finite() or result < 0:
        raise ModelResponseNormalizationError(
            "provider-reported cost must be a finite non-negative number"
        )
    return result


def normalize_usage(
    raw: Mapping[str, Any] | None,
    *,
    provider_reported_cost_usd: Any = None,
) -> LLMUsage:
    """Normalize a provider/LangChain usage mapping into :class:`LLMUsage`.

    Raises:
        ModelResponseNormalizationError: required token fields are absent, or any
            value is boolean, non-integral, negative, or otherwise malformed.
    """
    if not isinstance(raw, Mapping):
        raise ModelResponseNormalizationError("model response carried no usage metadata")

    has_input, input_raw = _first_present(raw, _INPUT_KEYS)
    has_output, output_raw = _first_present(raw, _OUTPUT_KEYS)
    if not has_input or not has_output:
        missing = "input_tokens" if not has_input else "output_tokens"
        raise ModelResponseNormalizationError(f"model response is missing required {missing}")

    input_tokens = _token_int(input_raw, "input_tokens")
    output_tokens = _token_int(output_raw, "output_tokens")

    has_total, total_raw = _first_present(raw, _TOTAL_KEYS)
    discrepancy = False
    if has_total:
        total_tokens = _token_int(total_raw, "total_tokens")
        if total_tokens != input_tokens + output_tokens:
            # Retain the provider total; flag the mismatch rather than "correct" it.
            discrepancy = True
    else:
        total_tokens = input_tokens + output_tokens

    has_cached, cached_raw = _first_present(raw, _CACHED_KEYS)
    cached = _token_int(cached_raw, "cached_input_tokens") if has_cached else None

    has_reasoning, reasoning_raw = _first_present(raw, _REASONING_KEYS)
    reasoning = _token_int(reasoning_raw, "reasoning_tokens") if has_reasoning else None

    if cached is not None and cached > input_tokens:
        raise ModelResponseNormalizationError(
            f"cached input tokens ({cached}) exceed input tokens ({input_tokens})"
        )
    if reasoning is not None and reasoning > output_tokens:
        raise ModelResponseNormalizationError(
            f"reasoning tokens ({reasoning}) exceed output tokens ({output_tokens})"
        )

    return LLMUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_input_tokens=cached,
        reasoning_tokens=reasoning,
        provider_reported_cost_usd=_cost(provider_reported_cost_usd),
        total_discrepancy=discrepancy,
    )
