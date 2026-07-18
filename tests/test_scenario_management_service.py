"""Application-service conversion and ownership tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from engine.comparison_engine import compare_model_outputs
from engine.ranking_engine import run_ranking_model
from engine.scenario_engine import apply_scenario_changes, build_scenario_changes
from persistence import AuthorizationError, SQLiteScenarioRepository
from services.scenario_management_service import ScenarioManagementService
from services.user_context import CurrentUser


def test_service_saves_executed_changes_and_selected_summaries(
    input_df: pd.DataFrame, tmp_path: Path
) -> None:
    repository = SQLiteScenarioRepository(tmp_path / "service.db")
    service = ScenarioManagementService(
        repository, CurrentUser("owner", "مالک", ("branch_user",))
    )
    baseline = run_ranking_model(input_df)
    branch_id = input_df.iloc[0]["branch_id"]
    edited = pd.DataFrame(
        [{"branch_id": branch_id, "avg_deposits": input_df.iloc[0]["avg_deposits"] * 1.1}]
    )
    changes = build_scenario_changes(input_df, edited)
    scenario_df = apply_scenario_changes(input_df, changes)
    scenario_outputs = run_ranking_model(scenario_df)
    comparison = compare_model_outputs(baseline, scenario_outputs)
    saved = service.save_executed(
        scenario_name="اجرای سرویس",
        baseline_period="1404-04",
        visibility="shared",
        selected_branch_ids=[branch_id],
        changes=changes,
        comparison=comparison,
        edit_modes={f"{branch_id}:avg_deposits": "percent"},
    )
    record, loaded_changes, summaries = service.load_scenario(saved.scenario_id)
    assert record.status == "executed"
    assert record.visibility == "shared"
    assert loaded_changes == changes
    assert len(summaries) == 1
    assert summaries[0].branch_id == branch_id
    _, _, _, edit_modes = service.load_scenario_editor(saved.scenario_id)
    assert edit_modes[f"{branch_id}:avg_deposits"] == "percent"


def test_non_owner_service_cannot_update_shared_scenario(tmp_path: Path) -> None:
    repository = SQLiteScenarioRepository(tmp_path / "ownership.db")
    owner = ScenarioManagementService(
        repository, CurrentUser("owner", "مالک", ("branch_user",))
    )
    other = ScenarioManagementService(
        repository, CurrentUser("other", "کاربر دیگر", ("branch_user",))
    )
    saved = owner.save_draft(
        scenario_name="مشترک",
        baseline_period="1404-04",
        visibility="shared",
        selected_branch_ids=[],
        changes=[],
    )
    with pytest.raises(AuthorizationError):
        other.save_draft(
            scenario_name="ویرایش غیرمجاز",
            baseline_period="1404-04",
            visibility="shared",
            selected_branch_ids=[],
            changes=[],
            scenario_id=saved.scenario_id,
            expected_row_version=saved.row_version,
        )
