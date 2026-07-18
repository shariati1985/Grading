"""Authoritative metadata and value-domain constraints for grading indicators."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Final


@dataclass(frozen=True)
class IndicatorDefinition:
    key: str
    display_name: str
    allow_negative: bool
    minimum_value: float | None
    direction: str = "benefit"


INDICATOR_REGISTRY: Final[dict[str, IndicatorDefinition]] = {
    "deposit_count": IndicatorDefinition("deposit_count", "تعداد سپرده‌ها", False, 0.0),
    "avg_deposits": IndicatorDefinition("avg_deposits", "میانگین سپرده‌ها", False, 0.0),
    "loan_count": IndicatorDefinition("loan_count", "تعداد تسهیلات", False, 0.0),
    "avg_loans": IndicatorDefinition("avg_loans", "میانگین تسهیلات", False, 0.0),
    "commitment_count": IndicatorDefinition("commitment_count", "تعداد تعهدات", False, 0.0),
    "avg_commitments": IndicatorDefinition("avg_commitments", "میانگین تعهدات", False, 0.0),
    "transaction_volume": IndicatorDefinition("transaction_volume", "حجم عملیات", False, 0.0),
    "profit_loss": IndicatorDefinition("profit_loss", "سود و زیان", True, None),
}

PROFIT_LOSS_KEY: Final[str] = "profit_loss"


def validate_indicator_value(indicator_key: str, value: object) -> str | None:
    """Return a validation code for an invalid final value, otherwise None."""
    if indicator_key not in INDICATOR_REGISTRY:
        return "UNKNOWN_INDICATOR"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "NON_NUMERIC_VALUE"
    if not math.isfinite(numeric):
        return "NON_FINITE_VALUE"
    minimum = INDICATOR_REGISTRY[indicator_key].minimum_value
    if minimum is not None and numeric < minimum:
        return "BELOW_MINIMUM"
    return None
