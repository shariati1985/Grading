"""Lightweight tests for application UI helpers."""

from pathlib import Path

from data.contracts import CANONICAL_COLUMNS
from ui import SESSION_DEFAULTS, initialize_session_state
from ui.data_access import load_dashboard_data
from ui.formatters import (
    format_grade,
    format_number,
    format_percentage,
    format_rank,
    format_rank_change,
    format_raw_value,
    format_score,
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


def test_session_state_initializer_is_complete_and_non_destructive() -> None:
    state: dict[str, object] = {"scenario_name": "سناریوی موجود"}
    initialized = initialize_session_state(state)
    assert set(SESSION_DEFAULTS).issubset(initialized)
    assert initialized["scenario_name"] == "سناریوی موجود"
    initialized["selected_branches"].append("101")  # type: ignore[union-attr]
    second: dict[str, object] = {}
    initialize_session_state(second)
    assert second["selected_branches"] == []


def test_dashboard_loads_repository_data_and_model_outputs() -> None:
    data, outputs = load_dashboard_data(ROOT / "Data.xlsx", "1404-04")
    assert tuple(data.columns) == CANONICAL_COLUMNS
    assert len(outputs.final_result) == len(data)
    assert list(outputs.final_result.columns) == [
        "branch_id", "branch_name", "region", "final_score", "rank", "grade"
    ]
