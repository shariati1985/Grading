"""Contract tests for reusable visual-layer helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from ui.charts import (
    IndicatorComparisonDataError,
    build_selected_indicator_score_chart,
    build_indicator_rank_lollipop,
    build_network_rank_chart,
    prepare_selected_indicator_scores,
    rank_axis_range,
    validate_indicator_score_chart_matches_table,
)
from ui.navigation import NAVIGATION_ITEMS
from ui.scenario_workflow import INDICATOR_LABELS, INDICATOR_ORDER


def _indicator_comparison() -> pd.DataFrame:
    rows = []
    for branch_offset, branch_id in enumerate(("101", "202")):
        for position, indicator_key in enumerate(reversed(INDICATOR_ORDER)):
            rows.append(
                {
                    "branch_id": branch_id,
                    "indicator_key": indicator_key,
                    "baseline_score": float(100 + position + branch_offset * 100),
                    "scenario_score": float(200 + position + branch_offset * 100),
                    "baseline_weighted_score": -10_000.0 - position,
                    "scenario_weighted_score": 10_000.0 + position,
                    "raw_value": 999_999_999.0,
                }
            )
    return pd.DataFrame(rows)


def test_rank_axis_range_has_minimum_and_expands_symmetrically() -> None:
    assert rank_axis_range([]) == (-3, 3)
    assert rank_axis_range([1, -1, 0]) == (-3, 3)
    assert rank_axis_range([4, -2]) == (-4, 4)


def test_indicator_rank_chart_uses_integer_ticks_and_centered_range() -> None:
    figure = build_indicator_rank_lollipop(
        pd.Series(["شاخص یک", "شاخص دو"]), pd.Series([1, -1])
    )
    assert figure.layout.xaxis.dtick == 1
    assert tuple(figure.layout.xaxis.range) == (-3, 3)
    assert figure.layout.height == 440


def test_indicator_score_chart_uses_exact_unweighted_scores_and_persian_order() -> None:
    source = _indicator_comparison()
    prepared = prepare_selected_indicator_scores(source, "101")
    figure = build_selected_indicator_score_chart(prepared)

    assert list(prepared.columns) == [
        "branch_id",
        "indicator_key",
        "baseline_score",
        "scenario_score",
    ]
    assert prepared["indicator_key"].tolist() == list(INDICATOR_ORDER)
    assert list(figure.data[0].x) == prepared["baseline_score"].tolist()
    assert list(figure.data[1].x) == prepared["scenario_score"].tolist()
    assert list(figure.data[0].y) == [INDICATOR_LABELS[key] for key in INDICATOR_ORDER]
    assert tuple(figure.layout.xaxis.range) == (1, 1000)
    assert "baseline_weighted_score" not in prepared.columns
    assert "scenario_weighted_score" not in prepared.columns
    assert max(figure.data[0].x) < 1000
    assert max(figure.data[1].x) < 1000


def test_indicator_score_chart_filters_selected_branch_and_has_eight_unique_rows() -> None:
    prepared = prepare_selected_indicator_scores(_indicator_comparison(), "202")
    assert prepared["branch_id"].eq("202").all()
    assert len(prepared) == 8
    assert prepared["indicator_key"].nunique() == 8


def test_indicator_chart_values_validate_against_table_values() -> None:
    prepared = prepare_selected_indicator_scores(_indicator_comparison(), "101")
    table_source = prepared.copy(deep=True)
    validate_indicator_score_chart_matches_table(prepared, table_source)
    table_source.loc[0, "scenario_score"] += 0.1
    with pytest.raises(IndicatorComparisonDataError, match="do not match"):
        validate_indicator_score_chart_matches_table(prepared, table_source)


def test_indicator_score_data_rejects_duplicates_and_out_of_range_scores() -> None:
    source = _indicator_comparison()
    duplicate = pd.concat([source, source.iloc[[0]]], ignore_index=True)
    with pytest.raises(IndicatorComparisonDataError, match="duplicate branch_id"):
        prepare_selected_indicator_scores(duplicate, "101")

    out_of_range = source.copy(deep=True)
    out_of_range.loc[
        out_of_range["branch_id"].eq("101"), "baseline_score"
    ] = 1001.0
    with pytest.raises(IndicatorComparisonDataError, match="within 1–1000"):
        prepare_selected_indicator_scores(out_of_range, "101")


def test_single_network_result_uses_compact_chart() -> None:
    network = pd.DataFrame(
        {
            "branch_id": ["101"],
            "branch_name": ["غدیر"],
            "rank_change": [1],
        }
    )
    figure = build_network_rank_chart(network, improvement=True)
    assert figure is not None
    assert figure.layout.height == 270
    assert figure.layout.xaxis.dtick == 1
    assert tuple(figure.layout.xaxis.range) == (0, 2)


def test_empty_network_result_returns_no_chart() -> None:
    network = pd.DataFrame(
        {"branch_id": ["101"], "branch_name": ["غدیر"], "rank_change": [0]}
    )
    assert build_network_rank_chart(network, improvement=True) is None
    assert build_network_rank_chart(network, improvement=False) is None


def test_persian_navigation_labels_and_icons_are_complete() -> None:
    assert [label for _, label, _ in NAVIGATION_ITEMS] == [
        "داشبورد",
        "ساخت سناریو",
        "نتایج سناریو",
        "اثر بر شبکه",
        "مقایسه سناریوها",
        "گزارش‌ها",
    ]
    assert all(icon.strip() for icon, _, _ in NAVIGATION_ITEMS)
