"""Profit/loss direction and branch-identity regression tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.ranking_engine import WEIGHTS, run_ranking_model
from engine.diagnostics import build_profit_loss_diagnostics


def _otherwise_identical(input_df: pd.DataFrame, profits: list[float]) -> pd.DataFrame:
    row = input_df.iloc[0].copy()
    rows = []
    for index, profit in enumerate(profits, start=1):
        item = row.copy()
        item["branch_id"] = str(index)
        item["branch_name"] = f"Branch {index}"
        item["profit_loss"] = profit
        rows.append(item)
    return pd.DataFrame(rows).reset_index(drop=True)


def test_higher_profit_loss_receives_better_indicator_score(input_df) -> None:
    outputs = run_ranking_model(_otherwise_identical(input_df, [-100.0, 0.0, 100.0]))
    scores = outputs.indicator_results.loc[
        outputs.indicator_results["indicator_key"].eq("profit_loss")
    ].set_index("branch_id")["score"]
    assert scores["3"] > scores["2"] > scores["1"]


def test_extreme_loss_is_not_better_than_zero_or_positive(input_df) -> None:
    outputs = run_ranking_model(
        _otherwise_identical(input_df, [-10_000_000_000_000.0, 0.0, 10_000.0])
    )
    scores = outputs.indicator_results.loc[
        outputs.indicator_results["indicator_key"].eq("profit_loss")
    ].set_index("branch_id")["score"]
    assert scores["1"] == 1.0
    assert scores["1"] < scores["2"] < scores["3"]


def test_sorted_outputs_keep_profit_and_score_aligned_by_branch_id(input_df) -> None:
    outputs = run_ranking_model(input_df.sample(frac=1.0, random_state=42).reset_index(drop=True))
    raw = outputs.raw_data.set_index("branch_id")["profit_loss"]
    indicators = outputs.indicator_results.loc[
        outputs.indicator_results["indicator_key"].eq("profit_loss")
    ].set_index("branch_id")
    assert indicators.index.is_unique
    pd.testing.assert_series_equal(
        indicators["raw_value"].sort_index(), raw.sort_index(), check_names=False
    )
    assert set(outputs.final_result["branch_id"]) == set(raw.index)


def test_fatemi_extreme_loss_has_near_bottom_indicator_rank(input_df) -> None:
    outputs = run_ranking_model(input_df)
    fatemi = outputs.indicator_results.loc[
        outputs.indicator_results["branch_name"].eq("فاطمی")
        & outputs.indicator_results["indicator_key"].eq("profit_loss")
    ].iloc[0]
    zero_or_better = outputs.indicator_results.loc[
        outputs.indicator_results["indicator_key"].eq("profit_loss")
        & outputs.indicator_results["raw_value"].ge(0)
    ]
    assert fatemi["raw_value"] < 0
    assert fatemi["indicator_rank"] >= len(input_df) - 1
    assert fatemi["score"] < zero_or_better["score"].min()


def test_full_bank_profit_loss_scores_are_monotonic_and_within_common_scale(input_df) -> None:
    outputs = run_ranking_model(input_df)
    diagnostic = build_profit_loss_diagnostics(outputs, outputs).sort_values(
        "raw_profit_loss"
    )
    assert diagnostic["normalized_profit_loss_score"].is_monotonic_increasing
    assert diagnostic["normalized_profit_loss_score"].between(1.0, 1000.0).all()
    assert diagnostic.iloc[0]["normalized_profit_loss_score"] == 1.0
    assert diagnostic.iloc[-1]["normalized_profit_loss_score"] == 1000.0


def test_displayed_score_is_normalized_not_weighted(input_df) -> None:
    outputs = run_ranking_model(input_df)
    diagnostic = build_profit_loss_diagnostics(outputs, outputs)
    assert diagnostic["displayed_profit_loss_score"].equals(
        diagnostic["normalized_profit_loss_score"]
    )
    expected_weighted = (
        diagnostic["normalized_profit_loss_score"] * diagnostic["profit_loss_weight"]
    )
    pd.testing.assert_series_equal(
        diagnostic["weighted_profit_loss_score"], expected_weighted, check_names=False
    )


def test_profit_loss_uses_official_shift_log_normalization(input_df) -> None:
    outputs = run_ranking_model(input_df)
    raw = outputs.raw_data["profit_loss"]
    shifted = raw + abs(float(raw.min())) + 1.0
    logs = np.log(shifted)
    expected_scores = ((logs - logs.min()) / (logs.max() - logs.min())) * 999.0 + 1.0

    pd.testing.assert_series_equal(
        outputs.shifted_values["profit_loss"], shifted, check_names=False
    )
    pd.testing.assert_series_equal(outputs.log_values["profit_loss"], logs, check_names=False)
    pd.testing.assert_series_equal(
        outputs.normalized_scores["profit_loss"], expected_scores, check_names=False
    )
    assert outputs.shifted_values["profit_loss"].gt(0).all()


def test_fatemi_official_profit_loss_trace(input_df) -> None:
    outputs = run_ranking_model(input_df)
    fatemi = outputs.indicator_results.loc[
        outputs.indicator_results["branch_id"].eq("103")
        & outputs.indicator_results["indicator_key"].eq("profit_loss")
    ].iloc[0]
    assert fatemi["shifted_value"] > 0
    assert fatemi["log_value"] == pytest.approx(np.log(fatemi["shifted_value"]), abs=1e-12)
    assert fatemi["score"] == pytest.approx(856.7019931, abs=1e-6)
    assert fatemi["weighted_score"] == pytest.approx(
        fatemi["score"] * WEIGHTS["profit_loss"], abs=1e-10
    )
    profit = outputs.indicator_results.loc[
        outputs.indicator_results["indicator_key"].eq("profit_loss")
    ]
    expected_rank = int(profit["score"].rank(method="first", ascending=False).loc[fatemi.name])
    assert fatemi["indicator_rank"] == expected_rank == 222
