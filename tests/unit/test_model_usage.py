"""Usage normalization matrix (design 7.4)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from agentscope.models.errors import ModelResponseNormalizationError
from agentscope.models.usage import LLMUsage, normalize_usage


def test_normal_prompt_completion_total() -> None:
    u = normalize_usage({"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
    assert (u.input_tokens, u.output_tokens, u.total_tokens) == (10, 5, 15)
    assert u.cached_input_tokens is None
    assert u.reasoning_tokens is None
    assert u.total_discrepancy is False


def test_openai_style_alias_keys() -> None:
    u = normalize_usage({"prompt_tokens": 3, "completion_tokens": 4})
    assert (u.input_tokens, u.output_tokens, u.total_tokens) == (3, 4, 7)


def test_total_absent_is_derived() -> None:
    u = normalize_usage({"input_tokens": 2, "output_tokens": 2})
    assert u.total_tokens == 4
    assert u.total_discrepancy is False


def test_provider_total_discrepancy_is_flagged_not_corrected() -> None:
    u = normalize_usage({"input_tokens": 2, "output_tokens": 2, "total_tokens": 99})
    assert u.total_tokens == 99
    assert u.total_discrepancy is True


def test_cached_and_reasoning_present() -> None:
    u = normalize_usage(
        {
            "input_tokens": 100,
            "output_tokens": 40,
            "cached_input_tokens": 30,
            "reasoning_tokens": 12,
        }
    )
    assert u.cached_input_tokens == 30
    assert u.reasoning_tokens == 12


def test_zero_tokens_preserved_as_zero_not_none() -> None:
    u = normalize_usage({"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0})
    assert u.input_tokens == 0
    assert u.cached_input_tokens == 0


def test_absent_optionals_stay_none() -> None:
    u = normalize_usage({"input_tokens": 1, "output_tokens": 1})
    assert u.cached_input_tokens is None
    assert u.reasoning_tokens is None


def test_missing_required_usage_fails() -> None:
    with pytest.raises(ModelResponseNormalizationError):
        normalize_usage({"input_tokens": 1})
    with pytest.raises(ModelResponseNormalizationError):
        normalize_usage(None)


@pytest.mark.parametrize(
    "raw",
    [
        {"input_tokens": -1, "output_tokens": 1},
        {"input_tokens": True, "output_tokens": 1},
        {"input_tokens": 1.5, "output_tokens": 1},
        {"input_tokens": "10", "output_tokens": 1},
        {"input_tokens": 1, "output_tokens": None},
    ],
)
def test_malformed_values_fail_normalization(raw: dict[str, object]) -> None:
    with pytest.raises(ModelResponseNormalizationError):
        normalize_usage(raw)


def test_provider_reported_cost_is_carried_as_decimal_when_supplied() -> None:
    u = normalize_usage(
        {"input_tokens": 1, "output_tokens": 1}, provider_reported_cost_usd="0.00123"
    )
    assert u.provider_reported_cost_usd == Decimal("0.00123")


@pytest.mark.parametrize("cost", ["-1", "NaN", "Infinity"])
def test_invalid_provider_cost_is_rejected(cost: str) -> None:
    with pytest.raises(ModelResponseNormalizationError):
        normalize_usage({"input_tokens": 1, "output_tokens": 1}, provider_reported_cost_usd=cost)


def test_usage_subdimensions_cannot_exceed_parent_dimension() -> None:
    with pytest.raises(ModelResponseNormalizationError):
        normalize_usage({"input_tokens": 1, "output_tokens": 1, "cached_input_tokens": 2})
    with pytest.raises(ModelResponseNormalizationError):
        normalize_usage({"input_tokens": 1, "output_tokens": 1, "reasoning_tokens": 2})


def test_usage_is_frozen() -> None:
    u = LLMUsage(input_tokens=1, output_tokens=1, total_tokens=2)
    with pytest.raises(Exception):  # noqa: B017
        u.input_tokens = 5  # type: ignore[misc]
