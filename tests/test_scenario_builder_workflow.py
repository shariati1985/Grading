"""Tests for Scenario Builder orchestration helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from engine.ranking_engine import run_ranking_model
from ui.scenario_workflow import (
    INDICATOR_ORDER,
    build_editor_data,
    execute_scenario,
    filter_network_impact,
    reset_scenario_state,
    selected_branch_results,
    synchronize_edited_values,
)


def test_build_editor_rows_for_one_branch(input_df: pd.DataFrame) -> None:
    branch_id = input_df.iloc[0]["branch_id"]
    editor = build_editor_data(input_df, [branch_id])
    assert len(editor) == 8
    assert editor["branch_id"].eq(branch_id).all()
    assert tuple(editor["indicator_key"]) == INDICATOR_ORDER
    assert editor["change_percent"].eq(0).all()
    assert editor["scenario_value"].equals(editor["baseline_value"])


def test_build_editor_rows_for_multiple_branches(input_df: pd.DataFrame) -> None:
    branch_ids = input_df.iloc[:2]["branch_id"].tolist()
    editor = build_editor_data(input_df, branch_ids)
    assert len(editor) == 16
    assert editor.groupby("branch_id", sort=False).size().to_dict() == {
        branch_ids[0]: 8,
        branch_ids[1]: 8,
    }


def test_no_change_scenario_produces_zero_differences(input_df: pd.DataFrame) -> None:
    baseline_outputs = run_ranking_model(input_df)
    branch_id = input_df.iloc[0]["branch_id"]
    execution = execute_scenario(
        input_df,
        baseline_outputs,
        build_editor_data(input_df, [branch_id]),
        "بدون تغییر",
        [branch_id],
    )
    assert execution.changes == []
    assert execution.comparison_results.branch_comparison["score_change"].eq(0).all()
    assert execution.comparison_results.branch_comparison["rank_change"].eq(0).all()
    assert execution.comparison_results.indicator_comparison["score_change"].eq(0).all()


def test_selected_branch_result_mapping_preserves_selection(input_df: pd.DataFrame) -> None:
    baseline_outputs = run_ranking_model(input_df)
    branch_ids = input_df.iloc[:2]["branch_id"].tolist()[::-1]
    execution = execute_scenario(
        input_df,
        baseline_outputs,
        build_editor_data(input_df, branch_ids),
        "نگاشت شعب",
        branch_ids,
    )
    selected = selected_branch_results(execution.comparison_results, branch_ids)
    assert selected["branch_id"].tolist() == branch_ids
    assert {"baseline_score", "scenario_score", "rank_change"}.issubset(selected.columns)


def test_rank_improvement_sign_is_positive(input_df: pd.DataFrame) -> None:
    baseline_outputs = run_ranking_model(input_df)
    branch_id = baseline_outputs.final_result.iloc[-1]["branch_id"]
    editor = build_editor_data(input_df, [branch_id])
    row = editor["indicator_key"].eq("avg_deposits")
    editor.loc[row, "scenario_value"] = input_df["avg_deposits"].max() * 10
    execution = execute_scenario(input_df, baseline_outputs, editor, "بهبود رتبه", [branch_id])
    selected = selected_branch_results(execution.comparison_results, [branch_id]).iloc[0]
    assert selected["rank_change"] == selected["baseline_rank"] - selected["scenario_rank"]
    assert selected["rank_change"] > 0


def test_network_impact_filters() -> None:
    network = pd.DataFrame(
        {
            "branch_id": ["1", "2", "3"],
            "rank_change": [2, -1, 0],
            "grade_changed": [False, True, False],
        }
    )
    assert filter_network_impact(network, "همه شعب")["branch_id"].tolist() == ["1", "2", "3"]
    assert filter_network_impact(network, "فقط شعب دارای تغییر رتبه")["branch_id"].tolist() == ["1", "2"]
    assert filter_network_impact(network, "فقط شعب دارای تغییر درجه")["branch_id"].tolist() == ["2"]
    assert filter_network_impact(network, "فقط شعب دارای بهبود رتبه")["branch_id"].tolist() == ["1"]
    assert filter_network_impact(network, "فقط شعب دارای افت رتبه")["branch_id"].tolist() == ["2"]


def test_reset_state_helper_preserves_baseline_outputs() -> None:
    baseline_marker = object()
    state = {
        "baseline_outputs": baseline_marker,
        "scenario_name": "فعال",
        "scenario_executed": True,
        "scenario_dataframe": object(),
        "selected_branches": ["101"],
        "_selected_branches_input": ["101"],
        "editor_version": 4,
    }
    reset_scenario_state(state)
    assert state["baseline_outputs"] is baseline_marker
    assert state["scenario_name"] == ""
    assert state["scenario_executed"] is False
    assert state["scenario_dataframe"] is None
    assert state["selected_branches"] == []
    assert "_selected_branches_input" not in state
    assert state["editor_version"] == 5


def test_negative_values_only_allowed_for_profit_loss(input_df: pd.DataFrame) -> None:
    branch_id = input_df.iloc[0]["branch_id"]
    editor = build_editor_data(input_df, [branch_id])
    deposits = editor["indicator_key"].eq("avg_deposits")
    editor.loc[deposits, "scenario_value"] = -1
    with pytest.raises(ValueError, match="فقط برای سود و زیان"):
        synchronize_edited_values(editor)

    editor = build_editor_data(input_df, [branch_id])
    profit = editor["indicator_key"].eq("profit_loss")
    editor.loc[profit, "scenario_value"] = -1_000
    synchronized = synchronize_edited_values(editor)
    assert synchronized.loc[profit, "scenario_value"].iloc[0] == -1_000


def test_scenario_value_is_source_of_truth_and_percentage_is_rounded(
    input_df: pd.DataFrame,
) -> None:
    branch_id = input_df.iloc[0]["branch_id"]
    editor = build_editor_data(input_df, [branch_id])
    row = editor["indicator_key"].eq("deposit_count")
    baseline = float(editor.loc[row, "baseline_value"].iloc[0])
    editor.loc[row, "change_percent"] = 50
    editor.loc[row, "scenario_value"] = baseline * 1.123456
    synchronized = synchronize_edited_values(editor)
    assert synchronized.loc[row, "scenario_value"].iloc[0] == pytest.approx(baseline * 1.123456)
    assert synchronized.loc[row, "change_percent"].iloc[0] == 12.35
