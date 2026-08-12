from domain.scenario_contracts import ScenarioType
from ui.multi_branch_state import (
    MULTI_BRANCH_STAGE_LABELS,
    MULTI_BRANCH_STAGE_ORDER,
    MULTI_BRANCH_STATE_KEY,
    MultiBranchStage,
    current_multi_branch_stage,
    initialize_multi_branch_state,
    move_to_multi_branch_stage,
    new_multi_branch_workspace,
    reset_multi_branch_state,
)
from ui.sensitivity_state import start_new_scenario
from ui.sensitivity_state import SENSITIVITY_DRAFT_KEY, new_scenario_draft


def test_multi_branch_state_is_isolated_from_frozen_branch_centric_draft() -> None:
    branch_draft = new_scenario_draft(ScenarioType.FOCUS_BRANCH_ONLY)
    branch_draft["focus_branch_id"] = "101"
    state = {SENSITIVITY_DRAFT_KEY: branch_draft}

    multi = initialize_multi_branch_state(state)
    multi["primary_branch_code"] = "202"
    reset_multi_branch_state(state)

    assert state[SENSITIVITY_DRAFT_KEY] is branch_draft
    assert state[SENSITIVITY_DRAFT_KEY]["focus_branch_id"] == "101"
    assert state[MULTI_BRANCH_STATE_KEY]["primary_branch_code"] is None


def test_multi_branch_entry_order_is_fixed() -> None:
    assert MULTI_BRANCH_STAGE_ORDER == (
        MultiBranchStage.SCENARIO_DETAILS,
        MultiBranchStage.GENERAL_RULES,
        MultiBranchStage.BRANCH_EXCEPTIONS,
        MultiBranchStage.PRIMARY_BRANCH_OVERRIDES,
        MultiBranchStage.REVIEW,
    )
    assert [MULTI_BRANCH_STAGE_LABELS[stage] for stage in MULTI_BRANCH_STAGE_ORDER] == [
        "مشخصات سناریو",
        "قواعد عمومی",
        "استثناهای شعب",
        "مقادیر شعبه اصلی",
        "بازبینی و اجرا",
    ]


def test_workflow_prevents_skipping_entry_stages() -> None:
    workspace = new_multi_branch_workspace()

    move_to_multi_branch_stage(workspace, MultiBranchStage.GENERAL_RULES)
    assert current_multi_branch_stage(workspace) is MultiBranchStage.GENERAL_RULES

    try:
        move_to_multi_branch_stage(workspace, MultiBranchStage.PRIMARY_BRANCH_OVERRIDES)
    except ValueError as exc:
        assert "به‌ترتیب" in str(exc)
    else:
        raise AssertionError("Skipping branch exceptions must not be allowed")

    move_to_multi_branch_stage(workspace, MultiBranchStage.BRANCH_EXCEPTIONS)
    move_to_multi_branch_stage(workspace, MultiBranchStage.PRIMARY_BRANCH_OVERRIDES)
    move_to_multi_branch_stage(workspace, MultiBranchStage.REVIEW)
    assert current_multi_branch_stage(workspace) is MultiBranchStage.REVIEW


def test_starting_new_multi_branch_scenario_discards_previous_workspace() -> None:
    state = {MULTI_BRANCH_STATE_KEY: {"scenario_name": "قبلی"}}
    start_new_scenario(state, ScenarioType.MULTI_BRANCH)
    assert MULTI_BRANCH_STATE_KEY not in state
