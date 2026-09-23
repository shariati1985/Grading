"""Tests for aggregation-only home dashboard presentation service."""

from __future__ import annotations

import pandas as pd

from services.home_dashboard_service import build_home_dashboard_overview


def _summary():
    return pd.DataFrame(
        [
            ["101", "101", "الف", "R1", "منطقه 1", "1404-04", "1404/04", 800.0, 1, "Excellent", 2, 1, "2026-01-01"],
            ["102", "102", "ب", "R1", "منطقه 1", "1404-04", "1404/04", 600.0, 2, "Grade 1", 1, -1, "2026-01-01"],
            ["201", "201", "ج", "R2", "منطقه 2", "1404-04", "1404/04", 400.0, 3, "Grade 2", pd.NA, pd.NA, "2026-01-01"],
        ],
        columns=[
            "branch_id","branch_code","branch_name","region_id","region_name",
            "period_id","period_label","final_score","final_rank","grade",
            "previous_rank","rank_change","calculation_timestamp",
        ],
    )


def _indicators():
    rows=[]
    for branch_id, values in {
        "101":{"avg_deposits":900.0,"avg_loans":700.0},
        "102":{"avg_deposits":700.0,"avg_loans":500.0},
        "201":{"avg_deposits":300.0,"avg_loans":200.0},
    }.items():
        for key, score in values.items():
            rows.append(
                [branch_id, branch_id, "1404-04", key, key, 1.0, 2.0, 3.0, score, 1, 0.5, score*0.5]
            )
    return pd.DataFrame(
        rows,
        columns=[
            "branch_id","branch_code","period_id","indicator_id","indicator_name",
            "raw_value","shifted_value","log_value","normalized_score",
            "indicator_rank","weight","weighted_contribution",
        ],
    )


def test_overview_respects_permitted_branch_scope():
    result = build_home_dashboard_overview(
        _summary(),
        _indicators(),
        period_id="1404-04",
        permitted_branch_ids={"101","102"},
    )

    assert result.branch_count == 2
    assert result.region_count == 1
    assert result.average_final_score == 700.0
    assert set(result.grade_distribution["grade"]) == {"Excellent", "Grade 1"}
    assert result.region_summary.iloc[0]["branch_count"] == 2
    assert set(result.rank_movers["branch_id"]) == {"101","102"}


def test_overview_does_not_create_rank_movers_without_history():
    summary = _summary()
    summary["previous_rank"] = pd.NA
    summary["rank_change"] = pd.NA

    result = build_home_dashboard_overview(
        summary,
        _indicators(),
        period_id="1404-04",
    )

    assert result.rank_movers.empty
