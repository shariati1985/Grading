"""Persian-facing display formatters for model values."""

from __future__ import annotations

import math
import re

GRADE_LABELS: dict[str, str] = {
    "Excellent Plus": "ممتاز ویژه",
    "Excellent": "ممتاز",
    "Grade 1": "درجه ۱",
    "Grade 2": "درجه ۲",
    "Grade 3": "درجه ۳",
}
_PERSIAN_DIGITS = str.maketrans("0123456789,.-", "۰۱۲۳۴۵۶۷۸۹٬٫−")


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


def persian_digits(value: object) -> str:
    """Render presentation text with Persian digits and separators."""
    return str(value).translate(_PERSIAN_DIGITS)


def format_persian_number(value: object, decimals: int = 0) -> str:
    """Format a finite number for Persian UI display without changing data."""
    return persian_digits(format_number(value, decimals=decimals))


def format_score(value: object) -> str:
    """Format a model score to one decimal place."""
    return format_number(value, decimals=1)


def format_raw_value(value: object) -> str:
    """Format monetary, volume, and count values without immaterial decimals."""
    return format_number(value, decimals=0)


def format_compact_number(value: object, max_decimals: int = 4) -> str:
    """Group large values while retaining only meaningful decimal places."""
    number = _finite_number(value)
    if number is None:
        return "—"
    rendered = f"{number:,.{max_decimals}f}"
    return rendered.rstrip("0").rstrip(".")


def format_managerial_number(value: object) -> str:
    """Abbreviate large card values while keeping exact values in details/tooltips."""
    number = _finite_number(value)
    if number is None:
        return "—"
    for threshold, label in ((1e12, "تریلیون"), (1e9, "میلیارد"), (1e6, "میلیون")):
        if abs(number) >= threshold:
            return f"{number / threshold:,.1f} {label}"
    return format_number(number, decimals=1).rstrip("0").rstrip(".")


_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫−",
    "01234567890123456789.-",
)
_SUPPORTED_GROUP_SEPARATORS = ",٬،'’_ \u00a0\u2009\u202f"


def format_editable_number(value: object) -> str:
    """Format analytically precise editable values."""
    return format_compact_number(value, max_decimals=6)


def format_raw_input_value(value: object) -> str:
    """Format raw scenario inputs as whole grouped values."""
    return format_raw_value(value)


def parse_formatted_number(value: object) -> float:
    """Parse grouped Latin/Persian numeric input into a finite float."""
    text = str(value).translate(_DIGIT_TRANSLATION).strip()
    text = re.sub(f"[{re.escape(_SUPPORTED_GROUP_SEPARATORS)}]", "", text)
    if not text or not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
        raise ValueError("مقدار واردشده باید یک عدد معتبر باشد.")
    number = float(text)
    if not math.isfinite(number):
        raise ValueError("مقدار واردشده باید یک عدد متناهی باشد.")
    return number


def parse_raw_input_value(value: object) -> float:
    """Parse a raw indicator value and discard immaterial decimal places."""
    return float(round(parse_formatted_number(value)))


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


def format_persian_percentage(value: object, decimals: int = 1) -> str:
    """Format a finite percentage for Persian UI display."""
    number = _finite_number(value)
    return "—" if number is None else f"{persian_digits(f'{number:,.{decimals}f}')}٪"


def format_signed_persian_number(value: object, decimals: int = 0) -> str:
    """Format signed display numbers with Persian digits and grouped magnitude."""
    number = _finite_number(value)
    if number is None:
        return "—"
    sign = "+" if number > 0 else ""
    return persian_digits(f"{sign}{number:,.{decimals}f}")


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
