"""Focused tests for the row-based scenario indicator editor model."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from engine.scenario_engine import ScenarioChange
from ui.scenario_workflow import (
    INDICATOR_ORDER,
    build_editor_data,
    build_indicator_editor_state,
    build_scenario_changes_from_editor_state,
    calculate_change_percent,
    calculate_scenario_value,
    indicator_widget_key,
    reset_all_indicator_rows,
    reset_indicator_row,
    restore_indicator_editor_state,
    update_indicator_editor_state,
)


def _state(input_df: pd.DataFrame, count: int = 1):
    branch_ids = input_df.iloc[:count]["branch_id"].tolist()
    return build_indicator_editor_state(build_editor_data(input_df, branch_ids))


@pytest.mark.parametrize(
    ("baseline", "percent", "expected"),
    [(100.0, 10.0, 110.0), (100.0, -25.0, 75.0), (-100.0, 10.0, -110.0), (0.0, 50.0, 0.0)],
)
def test_percent_calculation(baseline: float, percent: float, expected: float) -> None:
    assert calculate_scenario_value(baseline, percent) == pytest.approx(expected)


def test_direct_calculation_and_zero_baseline() -> None:
    assert calculate_change_percent(80.0, 100.0) == pytest.approx(25.0)
    assert calculate_change_percent(-100.0, -110.0) == pytest.approx(10.0)
    assert calculate_change_percent(0.0, 25.0) is None


def test_state_has_eight_ordered_rows_per_branch(input_df: pd.DataFrame) -> None:
    state = _state(input_df, 2)
    assert len(state) == 16
    first_id = str(input_df.iloc[0]["branch_id"])
    assert [row["indicator_key"] for row in state.values() if row["branch_id"] == first_id] == list(INDICATOR_ORDER)


def test_row_and_global_reset_are_scoped(input_df: pd.DataFrame) -> None:
    state = _state(input_df, 2)
    row_ids = list(state)
    for row_id in row_ids[:2]:
        state[row_id].update(edit_mode="direct", scenario_value=999.0)
    synchronized = update_indicator_editor_state(state)
    first = synchronized[row_ids[0]]
    row_reset = reset_indicator_row(
        synchronized, first["branch_id"], first["indicator_key"]
    )
    assert row_reset[row_ids[0]]["scenario_value"] == row_reset[row_ids[0]]["baseline_value"]
    assert row_reset[row_ids[0]]["edit_mode"] == "percent"
    assert row_reset[row_ids[1]]["scenario_value"] == 999.0

    all_reset = reset_all_indicator_rows(synchronized)
    assert all(row["scenario_value"] == row["baseline_value"] for row in all_reset.values())
    assert all(row["edit_mode"] == "percent" for row in all_reset.values())


def test_widget_keys_are_stable_and_collision_free() -> None:
    keys = {
        indicator_widget_key(branch, indicator, field)
        for branch in ("101", "102")
        for indicator in INDICATOR_ORDER
        for field in ("edit_mode", "change_percent", "scenario_value", "reset")
    }
    assert len(keys) == 2 * 8 * 4
    assert indicator_widget_key("101", "avg_deposits", "edit_mode") == "scenario_101_avg_deposits_edit_mode"


def test_restore_preserves_persisted_method_and_exact_value(input_df: pd.DataFrame) -> None:
    state = _state(input_df)
    row_id = next(iter(state))
    row = state[row_id]
    change = ScenarioChange(
        branch_id=row["branch_id"],
        branch_name=row["branch_name"],
        indicator_key=row["indicator_key"],
        baseline_value=row["baseline_value"],
        scenario_value=row["baseline_value"] * 1.123456789,
        absolute_change=row["baseline_value"] * 0.123456789,
        percentage_change=12.3456789,
    )
    restored = restore_indicator_editor_state(state, [change], {row_id: "percent"})
    assert restored[row_id]["edit_mode"] == "percent"
    assert restored[row_id]["scenario_value"] == change.scenario_value
    assert restored[row_id]["change_percent"] == change.percentage_change


def test_final_state_builds_percent_and_direct_changes(input_df: pd.DataFrame) -> None:
    state = _state(input_df)
    row_ids = list(state)
    state[row_ids[0]].update(edit_mode="percent", change_percent=10.0)
    state[row_ids[1]].update(
        edit_mode="direct", scenario_value=state[row_ids[1]]["baseline_value"] + 5.0
    )
    changes = build_scenario_changes_from_editor_state(state)
    assert len(changes) == 2
    assert changes[0].scenario_value == pytest.approx(changes[0].baseline_value * 1.1)
    assert changes[1].absolute_change == pytest.approx(5.0)


def test_zero_baseline_direct_change_uses_undefined_percentage(input_df: pd.DataFrame) -> None:
    state = _state(input_df)
    row_id = next(iter(state))
    state[row_id].update(baseline_value=0.0, edit_mode="direct", scenario_value=10.0)
    change = build_scenario_changes_from_editor_state(state)[0]
    assert math.isnan(change.percentage_change)
