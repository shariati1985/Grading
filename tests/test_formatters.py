"""Tests for Persian/English numeric display helpers."""

from __future__ import annotations

import pytest

from ui.formatters import (
    format_percentage,
    format_raw_input_value,
    format_raw_value,
    format_score,
    parse_raw_input_value,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("500,000,000,000", 500_000_000_000.0),
        ("۵۰۰٬۰۰۰٬۰۰۰٬۰۰۰", 500_000_000_000.0),
        ("۵۰۰،۰۰۰،۰۰۰،۰۰۰", 500_000_000_000.0),
        ("500 000 000 000", 500_000_000_000.0),
        ("-12,345.67", -12_346.0),
    ],
)
def test_raw_input_parses_digits_and_supported_separators(text: str, expected: float) -> None:
    assert parse_raw_input_value(text) == expected


def test_raw_values_are_grouped_without_decimals() -> None:
    assert format_raw_input_value(500000000000.45) == "500,000,000,000"
    assert format_raw_value(12.8) == "13"


def test_score_weight_and_percent_formatting_preserves_decimals() -> None:
    assert format_score(12.34) == "12.3"
    assert format_percentage(12.345, decimals=2) == "12.35٪"
