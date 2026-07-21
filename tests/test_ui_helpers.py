"""Lightweight tests for application UI helpers."""

from pathlib import Path

from data.contracts import CANONICAL_COLUMNS
from ui import SESSION_DEFAULTS, initialize_session_state
from ui.data_access import load_dashboard_data
from ui.formatters import (
    format_compact_number, format_editable_number, format_managerial_number,
    format_grade,
    format_number,
    format_percentage,
    format_rank,
    format_rank_change,
    format_raw_value,
    format_score,
    parse_formatted_number,
)

ROOT = Path(__file__).resolve().parents[1]


def test_formatters_cover_model_display_values() -> None:
    assert format_number(12345.6) == "12,346"
    assert format_score(712.34) == "712.3"
    assert format_percentage(12.34) == "12.34٪"
    assert format_rank_change(2) == "+2 رتبه صعود"
    assert format_rank_change(-3) == "3 رتبه نزول"
    assert format_rank_change(0) == "بدون تغییر"
    assert format_grade("Grade 1") == "درجه ۱"
    assert format_number(None) == "—"


def test_business_number_formatting_and_persian_labels() -> None:
    assert format_raw_value(1_937_706_908_545.17) == "1,937,706,908,545"
    assert format_score(607.14) == "607.1"
    assert format_percentage(10.321) == "10.32٪"
    assert format_rank(32.0) == "32"
    assert format_rank_change(4) == "+4 رتبه صعود"
    assert format_rank_change(-2) == "2 رتبه نزول"
    assert format_grade("Excellent Plus") == "ممتاز ویژه"


def test_grouped_editable_numbers_support_large_decimal_and_negative_values() -> None:
    assert format_compact_number(4_000_000_000_000.125) == "4,000,000,000,000.125"
    assert format_editable_number(-1_234_567.25) == "-1,234,567.25"
    assert parse_formatted_number("4,000,000,000,000.125") == 4_000_000_000_000.125
    assert parse_formatted_number("−۱٬۲۳۴٫۵") == -1234.5


def test_managerial_numbers_are_compact_for_large_and_negative_values() -> None:
    assert format_managerial_number(43_914_706_149_140) == "43.9 تریلیون"
    assert format_managerial_number(-2_500_000_000) == "-2.5 میلیارد"
    assert format_managerial_number(125.25) == "125.2"


def test_session_state_initializer_is_complete_and_non_destructive() -> None:
    state: dict[str, object] = {"scenario_name": "سناریوی موجود"}
    initialized = initialize_session_state(state)
    assert set(SESSION_DEFAULTS).issubset(initialized)
    assert initialized["scenario_name"] == "سناریوی موجود"
    initialized["selected_branch_ids"].append("101")  # type: ignore[union-attr]
    second: dict[str, object] = {}
    initialize_session_state(second)
    assert second["selected_branch_ids"] == []


def test_legacy_selected_branches_session_key_is_migrated() -> None:
    state: dict[str, object] = {"selected_branches": ["101", "202"]}
    initialize_session_state(state)
    assert state["selected_branch_ids"] == ["101", "202"]
    assert "selected_branches" not in state


def test_dashboard_loads_repository_data_and_model_outputs() -> None:
    data, outputs = load_dashboard_data(ROOT / "Data.xlsx", "1404-04")
    assert tuple(data.columns) == CANONICAL_COLUMNS
    assert len(outputs.final_result) == len(data)
    assert list(outputs.final_result.columns) == [
        "branch_id", "branch_name", "region", "final_score", "rank", "grade"
    ]
