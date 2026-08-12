"""End-to-end Branch-Centric UI and SQLite restoration checks."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from domain.scenario_contracts import ScenarioType
from persistence.sqlite_scenario_repository import SQLiteScenarioRepository
from services.scenario_execution_service import ScenarioExecutionService
from services.scenario_management_service import ScenarioManagementService
from services.scenario_workspace_service import ScenarioWorkspaceService
from services.user_context import CurrentUser
from ui.sensitivity_adapters import build_focus_request, focus_result_presentation
from ui.sensitivity_state import new_scenario_draft


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_BUILDER = ROOT / "pages" / "2_Scenario_Builder.py"


def _workspace(path):
    user = CurrentUser("integration.user", "کاربر آزمون", ("admin",))
    return ScenarioWorkspaceService(
        ScenarioManagementService(SQLiteScenarioRepository(path), user)
    )


def test_new_branch_centric_form_does_not_force_local_assigned_branch() -> None:
    at = AppTest.from_file(SCENARIO_BUILDER, default_timeout=30)
    at.session_state["sensitivity_draft"] = new_scenario_draft(ScenarioType.FOCUS_BRANCH_ONLY)
    at.session_state["sensitivity_session_history"] = []
    at.run()
    selector = next(item for item in at.selectbox if item.label == "جست‌وجو و انتخاب شعبه")
    assert selector.value is None
    assert at.session_state["sensitivity_draft"]["focus_branch_id"] is None


def test_sqlite_save_recreate_reopen_and_restore_real_focus_result(tmp_path, input_df) -> None:
    database = tmp_path / "scenarios.db"
    focus = str(input_df.iloc[0]["branch_id"])
    draft = new_scenario_draft(ScenarioType.FOCUS_BRANCH_ONLY)
    draft.update(
        scenario_name="سناریوی پایدار", focus_branch_id=focus,
        focus_branch_source="USER_SELECTED_BRANCH", current_step=4,
        selected_indicator_ids=["avg_deposits"],
    )
    draft["focus_changes"] = {
        "avg_deposits": {"operation": "PERCENT_CHANGE", "value": 10.0}
    }
    original = ScenarioExecutionService().execute(build_focus_request(draft), input_df)
    draft.update(execution_result=original, show_result=True)
    first_service = _workspace(database)
    saved = first_service.save_execution(draft)

    recreated_service = _workspace(database)
    loaded = recreated_service.load_focus_scenario(
        saved.scenario_id, baseline_data=input_df, periods=["1404-04"],
        restore_execution=True,
    )
    assert loaded.record.scenario_id == saved.scenario_id
    assert loaded.draft["focus_branch_id"] == focus
    assert loaded.draft["focus_changes"]["avg_deposits"] == {
        "operation": "PERCENT_CHANGE", "value": 10.0,
    }
    assert loaded.draft["show_result"] is True
    restored = loaded.draft["execution_result"]
    assert restored.focus_branch_comparison.scenario_rank == original.focus_branch_comparison.scenario_rank

    _, indicators = focus_result_presentation(restored.focus_branch_comparison)
    indicator = next(item for item in indicators if item["name"] == "میانگین سپرده‌ها")
    normalized_current = indicator["weighted"]["current_numeric"] / indicator["weighted"]["weight_factor"]
    normalized_scenario = indicator["weighted"]["scenario_numeric"] / indicator["weighted"]["weight_factor"]
    assert indicator["weighted"]["current_numeric"] == normalized_current * indicator["weighted"]["weight_factor"]
    assert indicator["weighted"]["scenario_numeric"] == normalized_scenario * indicator["weighted"]["weight_factor"]
    assert indicator["weighted"]["effect_numeric"] == (
        indicator["weighted"]["scenario_numeric"] - indicator["weighted"]["current_numeric"]
    )


def test_branch_centric_result_page_renders_rank_cards_without_internal_icon_text(input_df) -> None:
    focus = str(input_df.iloc[0]["branch_id"])
    draft = new_scenario_draft(ScenarioType.FOCUS_BRANCH_ONLY)
    draft.update(
        focus_branch_id=focus, current_step=4, selected_indicator_ids=["profit_loss"],
        focus_changes={"profit_loss": {"operation": "PERCENT_CHANGE", "value": 10.0}},
    )
    draft["execution_result"] = ScenarioExecutionService().execute(build_focus_request(draft), input_df)
    draft["show_result"] = True
    at = AppTest.from_file(SCENARIO_BUILDER, default_timeout=30)
    at.session_state["sensitivity_draft"] = draft
    at.session_state["sensitivity_session_history"] = []
    at.run()
    assert not at.exception
    visible = " ".join(item.value for item in at.markdown)
    assert "نتیجه در یک نگاه" in visible
    assert "جزئیات کامل محاسبات" in visible
    assert "امتیاز موزون فعلی" in visible
    assert "شعب متأثر در رتبه‌بندی" in visible
    assert "keyboard_ar" not in visible
    assert "rd_double_arrow_left" not in visible
