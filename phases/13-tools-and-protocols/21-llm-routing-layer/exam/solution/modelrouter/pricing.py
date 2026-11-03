"""The price sheet, and what one call costs in micro-dollars."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Price:
    """USD per 1M tokens, as exact decimals."""

    input_per_m: Decimal
    output_per_m: Decimal


# USD per 1M tokens (input, output); the lesson's demo rates
PRICES = {
    "openai/gpt-4o": Price(Decimal("5.00"), Decimal("15.00")),
    "openai/gpt-4o-mini": Price(Decimal("0.15"), Decimal("0.60")),
    "anthropic/claude-sonnet": Price(Decimal("3.00"), Decimal("15.00")),
    "anthropic/claude-haiku": Price(Decimal("0.80"), Decimal("4.00")),
    "google/gemini-pro": Price(Decimal("1.25"), Decimal("5.00")),
}


def cost_micros(price: Price, input_tokens: int, output_tokens: int) -> int:
    """What one call costs, in whole micro-dollars.

    A price in USD per 1M tokens is the same number in micro-dollars per token, so the exact
    cost is input_tokens * input_per_m + output_tokens * output_per_m micro-dollars. It is
    rounded once per call, half up, to a whole micro-dollar: 70 input tokens at 0.15 cost
    10.5 micro-dollars and are charged 11.
    """
    exact = price.input_per_m * input_tokens + price.output_per_m * output_tokens
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP))
