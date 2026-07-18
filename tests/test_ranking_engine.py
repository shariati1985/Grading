"""Regression and invariant tests for the official ranking engine."""

from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from branch_ranking_new_model import create_weights_sheet
from engine.ranking_engine import INDICATOR_KEYS, run_ranking_model
from engine.validation import (
    validate_grade_counts,
    validate_rank_sequence,
    validate_score_range,
    validate_top_three_excellent_plus,
)

ROOT = Path(__file__).resolve().parents[1]


def test_unaffected_engine_columns_match_current_output_workbook(input_df: pd.DataFrame) -> None:
    actual = run_ranking_model(input_df)
    expected = {
        sheet: pd.read_excel(ROOT / "Branch_Ranking_New_Model.xlsx", sheet_name=sheet)
        for sheet in [
            "Weighted_Matrix",
            "Normalized_Scores",
            "Log_Values",
            "Weights",
            "Grade_Distribution",
        ]
    }
    actual_sheets = {
        "Weighted_Matrix": actual.weighted_matrix,
        "Normalized_Scores": actual.normalized_scores,
        "Log_Values": actual.log_values,
        "Weights": create_weights_sheet(),
        "Grade_Distribution": actual.grade_distribution,
    }
    for frame in expected.values():
        if "branch_name" in frame:
            frame["branch_name"] = frame["branch_name"].astype(str)
        if "branch_id" in frame:
            frame["branch_id"] = frame["branch_id"].astype(str)
    for sheet, actual_frame in actual_sheets.items():
        expected_frame = expected[sheet]
        if sheet in {"Weighted_Matrix", "Normalized_Scores", "Log_Values"}:
            actual_frame = actual_frame.drop(columns="profit_loss")
            expected_frame = expected_frame.drop(columns="profit_loss")
        assert_frame_equal(
            actual_frame.reset_index(drop=True),
            expected_frame.reset_index(drop=True),
            check_dtype=False,
            rtol=1e-12,
            atol=1e-12,
        )

    assert set(actual.final_result["branch_id"]) == set(
        expected["Weighted_Matrix"]["branch_id"]
    )


def test_final_scores_are_in_range(input_df: pd.DataFrame) -> None:
    result = run_ranking_model(input_df).final_result
    assert validate_score_range(result)


def test_ranks_are_sequential(input_df: pd.DataFrame) -> None:
    result = run_ranking_model(input_df).final_result
    assert validate_rank_sequence(result)


def test_grade_counts_equal_total_branch_count(input_df: pd.DataFrame) -> None:
    result = run_ranking_model(input_df).final_result
    assert validate_grade_counts(result)


def test_exactly_top_three_are_excellent_plus(input_df: pd.DataFrame) -> None:
    result = run_ranking_model(input_df).final_result
    assert validate_top_three_excellent_plus(result)
    assert result["grade"].eq("Excellent Plus").sum() == 3


def test_indicator_ranks_cover_all_branches_and_indicators(input_df: pd.DataFrame) -> None:
    outputs = run_ranking_model(input_df)
    indicators = outputs.indicator_results
    assert list(indicators.columns) == [
        "branch_id",
        "branch_name",
        "region",
        "indicator_key",
        "raw_value",
        "log_value",
        "score",
        "weighted_score",
        "indicator_rank",
    ]
    assert set(indicators["indicator_key"]) == set(INDICATOR_KEYS)
    assert len(indicators) == len(outputs.final_result) * len(INDICATOR_KEYS)
    for _, group in indicators.groupby("indicator_key"):
        assert np.array_equal(np.sort(group["indicator_rank"]), np.arange(1, len(group) + 1))
