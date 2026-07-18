"""Persian-facing display formatters for model values."""

from __future__ import annotations

import math

GRADE_LABELS: dict[str, str] = {
    "Excellent Plus": "ممتاز ویژه",
    "Excellent": "ممتاز",
    "Grade 1": "درجه ۱",
    "Grade 2": "درجه ۲",
    "Grade 3": "درجه ۳",
}


def _finite_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def format_number(value: object, decimals: int = 0) -> str:
    """Format a finite number with grouping, or return a neutral dash."""
    number = _finite_number(value)
    return "—" if number is None else f"{number:,.{decimals}f}"


def format_score(value: object) -> str:
    """Format a model score to one decimal place."""
    return format_number(value, decimals=1)


def format_raw_value(value: object) -> str:
    """Format monetary, volume, and count values without immaterial decimals."""
    return format_number(value, decimals=0)


def format_rank(value: object) -> str:
    """Format a rank as an integer."""
    return format_number(value, decimals=0)


def format_rank_change(value: object) -> str:
    """Describe rank movement, where a positive value is improvement."""
    number = _finite_number(value)
    if number is None:
        return "—"
    movement = int(number)
    if movement > 0:
        return f"{movement:+d} رتبه صعود"
    if movement < 0:
        return f"{abs(movement)} رتبه نزول"
    return "بدون تغییر"


def format_percentage(value: object, decimals: int = 2) -> str:
    """Format a percentage value using the Persian percent sign."""
    number = _finite_number(value)
    return "—" if number is None else f"{number:,.{decimals}f}٪"


def format_grade(value: object) -> str:
    """Translate known internal grade labels for display."""
    if value is None:
        return "—"
    text = str(value)
    return GRADE_LABELS.get(text, text)
