"""Application-service conversion and ownership tests."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from engine.comparison_engine import compare_model_outputs
from engine.ranking_engine import run_ranking_model
from engine.scenario_engine import apply_scenario_changes, build_scenario_changes
from engine.scenario_engine import ScenarioChange
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
        selected_branch_ids=[branch_id],
        changes=changes,
        comparison=comparison,
        edit_modes={f"{branch_id}:avg_deposits": "percent"},
    )
    record, loaded_changes, summaries = service.load_scenario(saved.scenario_id)
    assert record.status == "executed"
    assert record.visibility == "private"
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
        selected_branch_ids=[],
        changes=[],
    )
    with pytest.raises(AuthorizationError):
        other.save_draft(
            scenario_name="ویرایش غیرمجاز",
            baseline_period="1404-04",
            selected_branch_ids=[],
            changes=[],
            scenario_id=saved.scenario_id,
            expected_row_version=saved.row_version,
        )


def test_legacy_shared_scenario_is_owner_only_for_every_operation(tmp_path: Path) -> None:
    repository = SQLiteScenarioRepository(tmp_path / "legacy-shared.db")
    owner = ScenarioManagementService(
        repository, CurrentUser("owner", "مالک", ("branch_user",))
    )
    other = ScenarioManagementService(
        repository, CurrentUser("other", "کاربر دیگر", ("branch_user",))
    )
    saved = owner.save_draft(
        scenario_name="سناریوی قدیمی",
        baseline_period="1404-04",
        selected_branch_ids=[],
        changes=[],
    )
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE scenario_header SET visibility = 'shared' WHERE scenario_id = ?",
            (saved.scenario_id,),
        )

    assert [item.scenario_id for item in owner.list_visible()] == [saved.scenario_id]
    assert other.list_visible() == []
    assert owner.load_scenario(saved.scenario_id)[0].scenario_id == saved.scenario_id
    with pytest.raises(AuthorizationError):
        other.load_scenario(saved.scenario_id)
    with pytest.raises(AuthorizationError):
        other.copy_scenario(saved.scenario_id, "کپی غیرمجاز")
    with pytest.raises(AuthorizationError):
        other.save_draft(
            scenario_name="ویرایش غیرمجاز",
            baseline_period="1404-04",
            selected_branch_ids=[],
            changes=[],
            scenario_id=saved.scenario_id,
            expected_row_version=saved.row_version,
        )
    with pytest.raises(AuthorizationError):
        other.archive_scenario(saved.scenario_id, saved.row_version)
    with pytest.raises(AuthorizationError):
        other.delete_scenario(saved.scenario_id, saved.row_version)


def test_service_rejects_invalid_non_profit_final_value(tmp_path: Path) -> None:
    service = ScenarioManagementService(
        SQLiteScenarioRepository(tmp_path / "invalid-domain.db"),
        CurrentUser("owner", "مالک", ("branch_user",)),
    )
    invalid = ScenarioChange(
        "101", "شعبه", "deposit_count", 10.0, -1.0, -11.0, -110.0
    )
    with pytest.raises(ValueError, match="deposit_count|تعداد سپرده"):
        service.save_draft(
            scenario_name="نامعتبر",
            baseline_period="1404-04",
            selected_branch_ids=["101"],
            changes=[invalid],
        )


def test_saved_scenario_preserves_focus_branch_metadata(tmp_path: Path) -> None:
    service = ScenarioManagementService(
        SQLiteScenarioRepository(tmp_path / "focus-metadata.db"),
        CurrentUser("staff", "کاربر ستادی", ("staff_user",)),
    )
    definition = {
        "schema_version": 2,
        "focus_branch_id": "2001",
        "focus_branch_source": "USER_SELECTED_BRANCH",
        "scenario_mode": "ONLY_USER_BRANCH",
    }
    saved = service.save_draft(
        scenario_name="سناریوی محوری زنجان",
        baseline_period="1404-04",
        selected_branch_ids=["2001"],
        changes=[],
        summary={"scenario_definition": definition},
    )
    loaded, _, _ = service.load_scenario(saved.scenario_id)
    assert loaded.summary["scenario_definition"]["focus_branch_id"] == "2001"
    assert (
        loaded.summary["scenario_definition"]["focus_branch_source"]
        == "USER_SELECTED_BRANCH"
    )
