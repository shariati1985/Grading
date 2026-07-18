"""Validation helpers for model inputs, outputs, and no-change scenarios."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from pandas.testing import assert_series_equal

from .ranking_engine import (
    BRANCH_ID,
    BRANCH_NAME,
    EXCELLENT_PLUS_COUNT,
    GRADE_PERCENTAGES,
    INDICATOR_KEYS,
    WEIGHTS,
    normalize_columns,
    normalize_text,
    prepare_input_data,
    run_ranking_model,
)


def validate_required_columns(df: pd.DataFrame) -> bool:
    """Raise when one or more model columns are absent."""
    normalize_columns(df)
    return True


def validate_duplicate_branch_names(df: pd.DataFrame) -> bool:
    """Raise when stable branch identifiers are duplicated."""
    data = prepare_input_data(df)
    duplicates = data.loc[data[BRANCH_ID].duplicated(keep=False), BRANCH_ID].unique()
    if len(duplicates):
        raise ValueError(f"Duplicate branch IDs: {', '.join(map(str, duplicates))}")
    return True


def validate_blank_branch_names(df: pd.DataFrame) -> bool:
    """Raise when a data row has a blank branch name."""
    normalized = normalize_columns(df)
    branch_names = normalized[BRANCH_NAME].map(normalize_text)
    if branch_names.eq("").any():
        raise ValueError("Blank branch names found")
    return True


def validate_indicator_values(df: pd.DataFrame) -> bool:
    """Raise for non-numeric/non-finite values or negative non-profit values."""
    normalized = normalize_columns(df)
    for key in INDICATOR_KEYS:
        numeric = pd.to_numeric(normalized[key], errors="coerce")
        if numeric.isna().any() or not np.isfinite(numeric).all():
            raise ValueError(f"Invalid numeric values in indicator: {key}")
        if key != "profit_loss" and numeric.lt(0).any():
            raise ValueError(f"Negative values are not allowed for indicator: {key}")
    return True


def validate_missing_branches(
    baseline_df: pd.DataFrame, branch_ids: list[str] | set[str] | pd.Series
) -> bool:
    """Raise when scenario branch IDs do not exist in baseline data."""
    known = set(prepare_input_data(baseline_df)[BRANCH_ID])
    missing = sorted({str(branch_id) for branch_id in branch_ids} - known)
    if missing:
        raise ValueError(f"Branches not found in baseline data: {', '.join(missing)}")
    return True


def validate_unknown_indicator_keys(indicator_keys: list[str] | set[str] | pd.Series) -> bool:
    """Raise when scenario edits refer to unsupported indicators."""
    unknown = sorted(set(indicator_keys) - set(INDICATOR_KEYS))
    if unknown:
        raise ValueError(f"Unknown indicator keys: {', '.join(map(str, unknown))}")
    return True


def validate_weight_total(weights: dict[str, float] = WEIGHTS) -> bool:
    """Raise unless weights total exactly one within floating tolerance."""
    if not math.isclose(sum(weights.values()), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"Weights must sum to 1; got {sum(weights.values()):.12f}")
    return True


def validate_score_range(final_result: pd.DataFrame) -> bool:
    """Raise unless every final score is in the inclusive 1-1000 range."""
    if not final_result["final_score"].between(1.0, 1000.0, inclusive="both").all():
        raise ValueError("Final scores must be between 1 and 1000")
    return True


def validate_rank_sequence(final_result: pd.DataFrame) -> bool:
    """Raise unless ranks are precisely 1 through the number of branches."""
    expected = np.arange(1, len(final_result) + 1)
    if not np.array_equal(final_result["rank"].to_numpy(), expected):
        raise ValueError("Ranks are not sequential")
    return True


def validate_grade_counts(final_result: pd.DataFrame) -> bool:
    """Raise unless every branch has exactly one recognized grade."""
    recognized = {"Excellent Plus", "Excellent", "Grade 1", "Grade 2", "Grade 3"}
    if final_result["grade"].isna().any() or not set(final_result["grade"]).issubset(recognized):
        raise ValueError("Missing or unknown grades found")
    if int(final_result["grade"].value_counts().sum()) != len(final_result):
        raise ValueError("Grade counts do not equal total branch count")
    return True


def validate_top_three_excellent_plus(final_result: pd.DataFrame) -> bool:
    """Raise unless precisely the first three ranks are Excellent Plus."""
    expected_count = min(EXCELLENT_PLUS_COUNT, len(final_result))
    plus = final_result.loc[final_result["grade"].eq("Excellent Plus"), "rank"].tolist()
    if plus != list(range(1, expected_count + 1)):
        raise ValueError("Excellent Plus must be assigned to exactly the top three branches")
    return True


def validate_no_change_scenario(baseline_df: pd.DataFrame) -> dict[str, bool]:
    """Run the same model twice and report deterministic no-change checks."""
    baseline = run_ranking_model(baseline_df)
    repeated = run_ranking_model(baseline_df.copy(deep=True))

    def identical(left: pd.Series, right: pd.Series) -> bool:
        try:
            assert_series_equal(left.reset_index(drop=True), right.reset_index(drop=True))
            return True
        except AssertionError:
            return False

    return {
        "identical_scores": identical(
            baseline.final_result["final_score"], repeated.final_result["final_score"]
        ),
        "identical_ranks": identical(baseline.final_result["rank"], repeated.final_result["rank"]),
        "identical_grades": identical(
            baseline.final_result["grade"], repeated.final_result["grade"]
        ),
        "identical_indicator_scores": identical(
            baseline.indicator_results["score"], repeated.indicator_results["score"]
        ),
        "identical_indicator_ranks": identical(
            baseline.indicator_results["indicator_rank"],
            repeated.indicator_results["indicator_rank"],
        ),
    }
