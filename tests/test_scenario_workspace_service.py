"""Controlled-migration tests for the three-mode persisted workspace."""

from __future__ import annotations

from dataclasses import replace
import json

import pytest

from domain.scenario_contracts import IndicatorChange, ScenarioRequest, ScenarioType
from engine.scenario_rule_engine import RuleOperation
from persistence.contracts import ConcurrencyError
from persistence.sqlite_scenario_repository import SQLiteScenarioRepository
from services.scenario_management_service import ScenarioManagementService
from services.scenario_execution_service import ScenarioExecutionService
from services.scenario_workspace_service import (
    PERSISTENCE_STATUS_LABELS, ScenarioWorkspaceService,
    restore_sensitivity_draft, serialize_sensitivity_draft,
)
from services.user_context import CurrentUser
from ui.sensitivity_adapters import build_target_comparison_request
from ui.sensitivity_state import new_scenario_draft


@pytest.fixture
def workspace(tmp_path):
    repository = SQLiteScenarioRepository(tmp_path / "workspace.db")
    user = CurrentUser("user.one", "کاربر یک", ("branch_user",))
    return ScenarioWorkspaceService(ScenarioManagementService(repository, user))


def _draft(mode: ScenarioType):
    draft = new_scenario_draft(mode)
    draft.update(scenario_name=f"سناریوی {mode.value}", focus_branch_id="103",
                 focus_branch_source="USER_SELECTED_BRANCH", current_step=3)
    if mode is ScenarioType.FOCUS_BRANCH_ONLY:
        draft.update(selected_indicator_ids=["avg_deposits"])
        draft["focus_changes"] = {"avg_deposits": {"operation": "PERCENT_CHANGE", "value": 5, "preview": 10}}
    elif mode is ScenarioType.MULTI_BRANCH:
        draft["bulk_rules"] = [{"target_scope": "ALL_BRANCHES", "indicator_id": "avg_loans",
                                "operation": "PERCENT_CHANGE", "value": 2,
                                "selected_branch_ids": [], "selected_regions": []}]
        draft["manual_overrides"] = [{"branch_id": "103", "indicator_id": "loan_count",
                                      "operation": "SET_VALUE", "value": 8}]
    else:
        draft.update(selected_indicator_ids=["profit_loss"])
        draft["target_rank_request"] = {"target_rank": 2, "max_growth_percent": 30}
    return draft


@pytest.mark.parametrize("mode", list(ScenarioType))
def test_draft_serialization_for_every_mode_excludes_transient_state(mode) -> None:
    draft = _draft(mode)
    draft.update(execution_result=object(), target_solution=object(), validation_errors=["x"])
    definition = serialize_sensitivity_draft(draft)
    assert definition["scenario_type"] == mode.value
    assert not {"execution_result", "target_solution", "validation_errors"} & definition.keys()
    assert "preview" not in definition.get("focus_changes", {}).get("avg_deposits", {})


@pytest.mark.parametrize("mode", list(ScenarioType))
def test_save_list_and_restore_real_drafts(workspace, mode) -> None:
    draft = _draft(mode)
    record = workspace.save_draft(draft)
    assert record.status == "draft" and draft["persistence"]["row_version"] == 1
    assert [item.scenario_id for item in workspace.list_scenarios()] == [record.scenario_id]
    loaded = workspace.load_scenario(record.scenario_id, branch_ids=["103"], periods=["1404-04"])
    assert loaded.draft["scenario_type"] is mode
    assert loaded.draft["current_step"] == (1 if mode is ScenarioType.TARGET_RANK else 3)
    assert loaded.draft["execution_result"] is None
    assert loaded.draft["entry_source"] == "saved"


def test_restore_cleans_incompatible_references_without_substitution() -> None:
    definition = serialize_sensitivity_draft(_draft(ScenarioType.FOCUS_BRANCH_ONLY))
    definition["focus_branch_id"] = "missing"
    definition["selected_indicator_ids"].append("removed_indicator")
    restored, warnings = restore_sensitivity_draft(definition, branch_ids=["103"], periods=["1404-05"])
    assert restored["focus_branch_id"] is None
    assert restored["selected_indicator_ids"] == ["avg_deposits"]
    assert len(warnings) == 3


def test_new_version_preserves_parent_and_lineage(workspace) -> None:
    parent = workspace.save_draft(_draft(ScenarioType.MULTI_BRANCH))
    child = workspace.create_new_version(parent.scenario_id)
    assert child.scenario_id != parent.scenario_id
    lineage = child.summary["phase3b_lineage"]
    assert lineage["parent_scenario_id"] == parent.scenario_id
    assert lineage["version_number"] == 2
    assert workspace.management.load_scenario(parent.scenario_id)[0].row_version == 1


def test_stale_save_is_rejected_and_does_not_overwrite(workspace) -> None:
    first = _draft(ScenarioType.TARGET_RANK)
    saved = workspace.save_draft(first)
    stale = _draft(ScenarioType.TARGET_RANK)
    stale["persistence"] = dict(first["persistence"])
    first["scenario_name"] = "ویرایش نشست اول"
    workspace.save_draft(first)
    stale["scenario_name"] = "ویرایش کهنه"
    with pytest.raises(ConcurrencyError):
        workspace.save_draft(stale)
    assert workspace.management.load_scenario(saved.scenario_id)[0].scenario_name == "ویرایش نشست اول"


def test_persian_status_labels_do_not_leak_enums() -> None:
    assert PERSISTENCE_STATUS_LABELS["draft"] == "پیش‌نویس"
    assert PERSISTENCE_STATUS_LABELS["conflict"] == "تعارض نسخه"
    assert all("_" not in label for label in PERSISTENCE_STATUS_LABELS.values())


def test_save_executed_uses_existing_official_result_without_reranking(workspace, input_df, monkeypatch) -> None:
    focus = str(input_df.iloc[0]["branch_id"])
    request = ScenarioRequest(
        ScenarioType.FOCUS_BRANCH_ONLY, "نتیجه رسمی", focus,
        period="1404-04",
        focus_branch_changes=(IndicatorChange("avg_deposits", RuleOperation.PERCENT_CHANGE, 5),),
    )
    official = ScenarioExecutionService().execute(request, input_df)
    draft = _draft(ScenarioType.FOCUS_BRANCH_ONLY)
    draft.update(scenario_name="نتیجه رسمی", focus_branch_id=focus, execution_result=official)
    monkeypatch.setattr("engine.ranking_engine.run_ranking_model", lambda *_: (_ for _ in ()).throw(AssertionError("must not rerank while saving")))
    saved = workspace.save_execution(draft)
    record, _, summaries = workspace.management.load_scenario(saved.scenario_id)
    assert record.status == "executed"
    assert summaries and any(item.branch_id == focus for item in summaries)


def test_target_rank_execution_saves_two_path_summary_and_updates_same_record(workspace, input_df) -> None:
    draft = new_scenario_draft(ScenarioType.TARGET_RANK)
    draft.update(
        scenario_name="رتبه هدف ذخیره",
        focus_branch_id="103",
        focus_branch_source="USER_SELECTED_BRANCH",
        selected_indicator_ids=["avg_deposits"],
        target_rank_request={"target_rank": 29},
        current_step=2,
    )
    draft["target_comparison_result"] = ScenarioExecutionService().solve_target_rank_comparison(
        build_target_comparison_request(draft), input_df
    )
    draft["target_execution_completed"] = True
    first = workspace.save_execution(draft)
    second = workspace.save_execution(draft)
    assert first.scenario_id == second.scenario_id
    assert first.status == second.status == "executed"
    assert (first.row_version, second.row_version) == (1, 2)
    assert len(workspace.list_scenarios(search="رتبه هدف ذخیره")) == 1
    summary = second.summary["target_rank_result_summary"]
    assert sorted(summary["paths"]) == ["all_indicators_balanced", "user_selected_balanced"]
    assert second.summary["has_saved_result"] is True
    json.dumps(second.summary, ensure_ascii=False, allow_nan=False)
    assert "raw_data" not in json.dumps(second.summary, ensure_ascii=False)
    loaded = workspace.load_target_scenario(
        second.scenario_id, baseline_data=input_df, periods=["1404-04"], restore_execution=True
    )
    assert loaded.draft["current_step"] == 2
    assert loaded.draft["target_execution_completed"] is True
    assert loaded.draft["target_comparison_result"].balanced_all_indicators.path.display_name == "مسیر متوازن همه شاخص‌ها"
    assert loaded.draft["target_comparison_result"].user_selected_indicators.path.display_name == "مسیر شاخص‌های منتخب کاربر"


def test_empty_workspace_has_no_fake_persisted_history(workspace) -> None:
    assert workspace.list_scenarios() == []


def test_branch_centric_saved_scenario_can_be_deleted_after_confirmation_service_call(workspace) -> None:
    saved = workspace.save_draft(_draft(ScenarioType.FOCUS_BRANCH_ONLY))
    workspace.delete_scenario(saved.scenario_id, saved.row_version)
    assert workspace.list_scenarios() == []


def test_editing_an_executed_record_creates_new_draft_version(workspace, input_df) -> None:
    focus = str(input_df.iloc[0]["branch_id"])
    request = ScenarioRequest(
        ScenarioType.FOCUS_BRANCH_ONLY, "نسخه اجراشده", focus, period="1404-04",
        focus_branch_changes=(IndicatorChange("avg_deposits", RuleOperation.PERCENT_CHANGE, 5),),
    )
    draft = _draft(ScenarioType.FOCUS_BRANCH_ONLY)
    draft.update(scenario_name="نسخه اجراشده", focus_branch_id=focus,
                 execution_result=ScenarioExecutionService().execute(request, input_df))
    parent = workspace.save_execution(draft)
    draft["scenario_name"] = "نسخه قابل ویرایش"
    child = workspace.save_draft(draft)
    assert child.scenario_id != parent.scenario_id and child.status == "draft"
    assert child.summary["phase3b_lineage"]["parent_scenario_id"] == parent.scenario_id
    assert workspace.management.load_scenario(parent.scenario_id)[0].status == "executed"
