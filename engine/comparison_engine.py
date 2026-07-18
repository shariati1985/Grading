"""Compare baseline and scenario model outputs."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .ranking_engine import BRANCH_ID, BRANCH_NAME, IDENTITY_COLUMNS, REGION, ModelOutputs


@dataclass(frozen=True)
class ScenarioComparison:
    """Branch, indicator, network, grade, and summary scenario impacts."""

    branch_comparison: pd.DataFrame
    indicator_comparison: pd.DataFrame
    network_impact: pd.DataFrame
    grade_changes: pd.DataFrame
    summary: dict[str, int | float]


def _require_same_keys(left: pd.DataFrame, right: pd.DataFrame, keys: list[str]) -> None:
    left_keys = set(map(tuple, left[keys].to_numpy()))
    right_keys = set(map(tuple, right[keys].to_numpy()))
    if left_keys != right_keys:
        raise ValueError("Baseline and scenario outputs do not contain the same branches/indicators")


def compare_model_outputs(
    baseline: ModelOutputs, scenario: ModelOutputs
) -> ScenarioComparison:
    """Calculate branch and indicator effects; rank improvement is positive."""
    _require_same_keys(baseline.final_result, scenario.final_result, [BRANCH_ID])
    baseline_branches = baseline.final_result.rename(
        columns={
            "final_score": "baseline_score",
            "rank": "baseline_rank",
            "grade": "baseline_grade",
        }
    )
    scenario_branches = scenario.final_result.drop(columns=[BRANCH_NAME, REGION]).rename(
        columns={
            "final_score": "scenario_score",
            "rank": "scenario_rank",
            "grade": "scenario_grade",
        }
    )
    branch_comparison = baseline_branches.merge(
        scenario_branches, on=BRANCH_ID, how="inner", validate="one_to_one"
    )
    branch_comparison["score_change"] = (
        branch_comparison["scenario_score"] - branch_comparison["baseline_score"]
    )
    branch_comparison["rank_change"] = (
        branch_comparison["baseline_rank"] - branch_comparison["scenario_rank"]
    )
    branch_comparison["grade_changed"] = ~branch_comparison["baseline_grade"].eq(
        branch_comparison["scenario_grade"]
    )
    branch_columns = [
        *IDENTITY_COLUMNS,
        "baseline_score",
        "scenario_score",
        "score_change",
        "baseline_rank",
        "scenario_rank",
        "rank_change",
        "baseline_grade",
        "scenario_grade",
        "grade_changed",
    ]
    branch_comparison = branch_comparison.loc[:, branch_columns].sort_values("baseline_rank")

    keys = [BRANCH_ID, "indicator_key"]
    _require_same_keys(baseline.indicator_results, scenario.indicator_results, keys)
    baseline_indicators = baseline.indicator_results.rename(
        columns={
            "raw_value": "baseline_raw_value",
            "score": "baseline_score",
            "indicator_rank": "baseline_indicator_rank",
            "weighted_score": "baseline_weighted_score",
        }
    ).drop(columns=["log_value"])
    scenario_indicators = scenario.indicator_results.drop(columns=[BRANCH_NAME, REGION]).rename(
        columns={
            "raw_value": "scenario_raw_value",
            "score": "scenario_score",
            "indicator_rank": "scenario_indicator_rank",
            "weighted_score": "scenario_weighted_score",
        }
    ).drop(columns=["log_value"])
    indicators = baseline_indicators.merge(
        scenario_indicators, on=keys, how="inner", validate="one_to_one"
    )
    indicators["raw_value_change"] = (
        indicators["scenario_raw_value"] - indicators["baseline_raw_value"]
    )
    both_raw_missing = indicators["baseline_raw_value"].isna() & indicators[
        "scenario_raw_value"
    ].isna()
    indicators.loc[both_raw_missing, "raw_value_change"] = 0.0
    indicators["raw_value_change_pct"] = np.where(
        indicators["baseline_raw_value"].notna() & indicators["baseline_raw_value"].ne(0),
        indicators["raw_value_change"] / indicators["baseline_raw_value"] * 100.0,
        np.where(both_raw_missing, 0.0, np.nan),
    )
    indicators["score_change"] = indicators["scenario_score"] - indicators["baseline_score"]
    indicators["indicator_rank_change"] = (
        indicators["baseline_indicator_rank"] - indicators["scenario_indicator_rank"]
    )
    indicators["weighted_score_change"] = (
        indicators["scenario_weighted_score"] - indicators["baseline_weighted_score"]
    )
    indicator_columns = [
        *IDENTITY_COLUMNS,
        "indicator_key",
        "baseline_raw_value",
        "scenario_raw_value",
        "raw_value_change",
        "raw_value_change_pct",
        "baseline_score",
        "scenario_score",
        "score_change",
        "baseline_indicator_rank",
        "scenario_indicator_rank",
        "indicator_rank_change",
        "baseline_weighted_score",
        "scenario_weighted_score",
        "weighted_score_change",
    ]
    indicator_comparison = indicators.loc[:, indicator_columns]

    network_impact = branch_comparison.copy(deep=True)
    grade_changes = branch_comparison.loc[branch_comparison["grade_changed"]].copy()
    summary: dict[str, int | float] = {
        "total_branches": len(branch_comparison),
        "branches_with_rank_change": int(branch_comparison["rank_change"].ne(0).sum()),
        "branches_with_score_change": int(
            (~np.isclose(branch_comparison["score_change"], 0.0)).sum()
        ),
        "branches_with_grade_change": len(grade_changes),
        "largest_rank_improvement": int(branch_comparison["rank_change"].max()),
        "largest_rank_decline": int(branch_comparison["rank_change"].min()),
        "largest_score_increase": float(branch_comparison["score_change"].max()),
        "largest_score_decrease": float(branch_comparison["score_change"].min()),
    }
    return ScenarioComparison(
        branch_comparison=branch_comparison.reset_index(drop=True),
        indicator_comparison=indicator_comparison.reset_index(drop=True),
        network_impact=network_impact.reset_index(drop=True),
        grade_changes=grade_changes.reset_index(drop=True),
        summary=summary,
    )
