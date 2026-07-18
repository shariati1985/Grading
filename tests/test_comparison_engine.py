"""Tests for baseline-to-scenario comparison outputs."""

import pandas as pd

from engine.comparison_engine import compare_model_outputs
from engine.ranking_engine import run_ranking_model
from engine.scenario_engine import apply_scenario_changes, build_scenario_changes
from engine.validation import validate_no_change_scenario


def test_no_change_scenario_produces_zero_differences(input_df: pd.DataFrame) -> None:
    baseline = run_ranking_model(input_df)
    scenario = run_ranking_model(baseline.raw_data.copy(deep=True))
    comparison = compare_model_outputs(baseline, scenario)
    assert comparison.branch_comparison["score_change"].eq(0).all()
    assert comparison.branch_comparison["rank_change"].eq(0).all()
    assert not comparison.branch_comparison["grade_changed"].any()
    assert comparison.indicator_comparison["raw_value_change"].eq(0).all()
    assert comparison.indicator_comparison["score_change"].eq(0).all()
    assert comparison.indicator_comparison["indicator_rank_change"].eq(0).all()
    assert len(comparison.network_impact) == len(baseline.final_result)
    assert comparison.grade_changes.empty
    assert all(validate_no_change_scenario(input_df).values())


def test_rank_improvement_is_positive_and_network_includes_every_branch(
    input_df: pd.DataFrame,
) -> None:
    baseline = run_ranking_model(input_df)
    last_branch_id = baseline.final_result.iloc[-1]["branch_id"]
    edited = pd.DataFrame(
        [{"branch_id": last_branch_id, "avg_deposits": baseline.raw_data["avg_deposits"].max() * 10}]
    )
    scenario_df = apply_scenario_changes(
        baseline.raw_data, build_scenario_changes(baseline.raw_data, edited)
    )
    comparison = compare_model_outputs(baseline, run_ranking_model(scenario_df))
    changed = comparison.branch_comparison.set_index("branch_id").loc[last_branch_id]
    assert changed["rank_change"] == changed["baseline_rank"] - changed["scenario_rank"]
    assert changed["rank_change"] > 0
    assert len(comparison.network_impact) == len(baseline.final_result)
