"""Tests for scenario change construction and application."""

import pandas as pd
from pandas.testing import assert_frame_equal

from engine.ranking_engine import run_ranking_model
from engine.scenario_engine import (
    ScenarioChange,
    apply_scenario_changes,
    build_scenario_changes,
)


def test_one_branch_change_does_not_modify_baseline(input_df: pd.DataFrame) -> None:
    baseline = run_ranking_model(input_df).raw_data
    original = baseline.copy(deep=True)
    branch_id = baseline.iloc[0]["branch_id"]
    edited = pd.DataFrame(
        [{"branch_id": branch_id, "avg_deposits": baseline.iloc[0]["avg_deposits"] * 1.1}]
    )
    scenario = apply_scenario_changes(baseline, build_scenario_changes(baseline, edited))
    assert_frame_equal(baseline, original)
    assert scenario.loc[scenario["branch_id"].eq(branch_id), "avg_deposits"].iloc[0] != original.iloc[0][
        "avg_deposits"
    ]
    assert len(scenario) == len(baseline)


def test_multiple_branches_can_be_changed(input_df: pd.DataFrame) -> None:
    baseline = run_ranking_model(input_df).raw_data
    edited = pd.DataFrame(
        [
            {"branch_id": baseline.iloc[0]["branch_id"], "loan_count": 700.0},
            {"branch_id": baseline.iloc[1]["branch_id"], "deposit_count": 80000.0},
        ]
    )
    changes = build_scenario_changes(baseline, edited)
    scenario = apply_scenario_changes(baseline, changes)
    assert len(changes) == 2
    assert scenario.loc[0, "loan_count"] == 700.0
    assert scenario.loc[1, "deposit_count"] == 80000.0


def test_profit_loss_may_be_negative(input_df: pd.DataFrame) -> None:
    baseline = run_ranking_model(input_df).raw_data
    branch_id = baseline.iloc[0]["branch_id"]
    branch_name = baseline.iloc[0]["branch_name"]
    current = float(baseline.iloc[0]["profit_loss"])
    change = ScenarioChange(
        branch_id, branch_name, "profit_loss", current, -1_000.0, -1_000.0 - current, -100.0
    )
    scenario = apply_scenario_changes(baseline, [change])
    assert scenario.loc[scenario["branch_id"].eq(branch_id), "profit_loss"].iloc[0] == -1_000.0
    assert run_ranking_model(scenario).final_result["final_score"].between(1, 1000).all()
