"""Cost precedence, decimal arithmetic, and explicit unknown (design 7.5, D7)."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from agentscope.models.cost import CostSource, LLMCost, PriceCard, calculate_cost
from agentscope.models.usage import LLMUsage


def _usage(**over: object) -> LLMUsage:
    base: dict[str, object] = {"input_tokens": 1_000, "output_tokens": 500, "total_tokens": 1_500}
    base.update(over)
    return LLMUsage(**base)  # type: ignore[arg-type]


def _card(**over: object) -> PriceCard:
    base: dict[str, object] = {
        "pricing_id": "meta-muse",
        "version": "2026-01",
        "input_usd_per_mtok": "1.00",
        "output_usd_per_mtok": "2.00",
    }
    base.update(over)
    return PriceCard(**base)  # type: ignore[arg-type]


def test_provider_reported_cost_wins_over_pricing() -> None:
    c = calculate_cost(_usage(), _card(), provider_authoritative_cost="0.42")
    assert c.source is CostSource.PROVIDER_REPORTED
    assert c.amount_usd == Decimal("0.42")


def test_configured_input_output_calculation() -> None:
    c = calculate_cost(_usage(), _card())
    # 1000 * 1 / 1e6 + 500 * 2 / 1e6 = 0.001 + 0.001 = 0.002
    assert c.source is CostSource.CONFIGURED_PRICING
    assert c.amount_usd == Decimal("0.002")
    assert c.pricing_identity == "meta-muse#unknown"
    assert c.pricing_version == "2026-01"


def test_cached_input_discounted_calculation() -> None:
    card = _card(cached_input_usd_per_mtok="0.25")
    c = calculate_cost(_usage(cached_input_tokens=400), card)
    # uncached 600*1 + cached 400*0.25 + output 500*2 = 600 + 100 + 1000 = 1700 / 1e6
    assert c.amount_usd == Decimal("0.0017")


def test_cached_tokens_with_fallback_to_input_rate_policy() -> None:
    card = _card(cached_policy="input_rate")
    c = calculate_cost(_usage(cached_input_tokens=400), card)
    # cached billed at input rate -> same as no cache: 1000*1 + 500*2 = 2000 / 1e6
    assert c.amount_usd == Decimal("0.002")


def test_cached_tokens_with_unknown_cost_policy() -> None:
    c = calculate_cost(_usage(cached_input_tokens=400), _card())  # default policy: unknown
    assert c.source is CostSource.UNKNOWN
    assert c.amount_usd is None
    assert c.pricing_identity == "meta-muse#unknown"


def test_missing_price_card_is_unknown_not_zero() -> None:
    c = calculate_cost(_usage(), None)
    assert c.source is CostSource.UNKNOWN
    assert c.amount_usd is None


def test_zero_tokens_with_known_pricing_is_known_zero() -> None:
    c = calculate_cost(_usage(input_tokens=0, output_tokens=0, total_tokens=0), _card())
    assert c.source is CostSource.CONFIGURED_PRICING
    assert c.amount_usd == Decimal("0")


def test_no_premature_rounding_and_decimal_precision() -> None:
    card = _card(input_usd_per_mtok="0.333333", output_usd_per_mtok="0")
    c = calculate_cost(_usage(input_tokens=1, output_tokens=0, total_tokens=1), card)
    assert c.amount_usd == Decimal("0.333333") / Decimal(1_000_000)


def test_serialization_uses_decimal_string() -> None:
    c = LLMCost(amount_usd=Decimal("0.002"), source=CostSource.CONFIGURED_PRICING)
    dumped = c.model_dump(mode="json")
    assert dumped["amount_usd"] == "0.002"
    json.dumps(dumped)


def test_negative_rate_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _card(input_usd_per_mtok="-1")


def test_negative_authoritative_cost_is_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_cost(_usage(), None, provider_authoritative_cost="-0.01")


def test_cached_greater_than_input_is_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_cost(_usage(input_tokens=100, cached_input_tokens=200), _card())
