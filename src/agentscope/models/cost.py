"""Deterministic cost with explicit provenance (design 7.5, D7).

Cost has both a value and a source:

* ``provider_reported`` — a provider-profile extractor documented as authoritative
  for the call; it always wins.
* ``configured_pricing`` — computed from a versioned :class:`PriceCard`.
* ``unknown`` — neither exists; represented as ``amount_usd=None`` and source
  ``unknown``, never ``0.0``.

All arithmetic is :class:`~decimal.Decimal`. Provider numeric values are taken
through their string representation. Nothing is rounded during accumulation.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentscope.models.usage import LLMUsage

__all__ = ["CostSource", "LLMCost", "PriceCard", "calculate_cost"]

_PER_MTOK = Decimal(1_000_000)


class CostSource(StrEnum):
    """Where an :class:`LLMCost` value came from."""

    PROVIDER_REPORTED = "provider_reported"
    CONFIGURED_PRICING = "configured_pricing"
    UNKNOWN = "unknown"


class PriceCard(BaseModel):
    """A versioned USD-per-one-million-tokens price card."""

    model_config = ConfigDict(frozen=True)

    pricing_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    input_usd_per_mtok: Decimal = Field(ge=0, allow_inf_nan=False)
    output_usd_per_mtok: Decimal = Field(ge=0, allow_inf_nan=False)
    cached_input_usd_per_mtok: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    # Policy applied when cached input tokens exist but no cached rate is set.
    # The choice is part of the pricing identity.
    cached_policy: str = Field(default="unknown", pattern=r"^(input_rate|unknown)$")

    @property
    def identity(self) -> str:
        """Stable pricing identity, including the cached-token policy."""
        return f"{self.pricing_id}#{self.cached_policy}"


class LLMCost(BaseModel):
    """A normalized cost: value (or ``None``), source, and pricing identity."""

    model_config = ConfigDict(frozen=True)

    amount_usd: Decimal | None = Field(allow_inf_nan=False)
    source: CostSource
    pricing_identity: str | None = None
    pricing_version: str | None = None

    @classmethod
    def unknown(cls, pricing_identity: str | None = None) -> LLMCost:
        return cls(amount_usd=None, source=CostSource.UNKNOWN, pricing_identity=pricing_identity)


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{label} is not a valid decimal: {value!r}") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{label} must be a finite non-negative decimal: {result}")
    return result


def calculate_cost(
    usage: LLMUsage,
    price_card: PriceCard | None,
    *,
    provider_authoritative_cost: Any = None,
) -> LLMCost:
    """Resolve cost by precedence: authoritative provider cost, then pricing, then unknown.

    Raises:
        ValueError: a negative authoritative cost, or cached input tokens that
            exceed total input tokens.
    """
    if provider_authoritative_cost is not None:
        return LLMCost(
            amount_usd=_decimal(provider_authoritative_cost, "provider cost"),
            source=CostSource.PROVIDER_REPORTED,
        )

    if price_card is None:
        return LLMCost.unknown()

    cached = usage.cached_input_tokens or 0
    if cached > usage.input_tokens:
        raise ValueError(
            f"cached input tokens ({cached}) exceed input tokens ({usage.input_tokens})"
        )
    uncached_input = usage.input_tokens - cached

    if cached > 0 and price_card.cached_input_usd_per_mtok is None:
        if price_card.cached_policy == "input_rate":
            cached_rate = price_card.input_usd_per_mtok
        else:
            return LLMCost.unknown(price_card.identity)
    else:
        cached_rate = price_card.cached_input_usd_per_mtok or Decimal(0)

    total = (
        Decimal(uncached_input) * price_card.input_usd_per_mtok
        + Decimal(cached) * cached_rate
        + Decimal(usage.output_tokens) * price_card.output_usd_per_mtok
    ) / _PER_MTOK

    return LLMCost(
        amount_usd=total,
        source=CostSource.CONFIGURED_PRICING,
        pricing_identity=price_card.identity,
        pricing_version=price_card.version,
    )
