"""Pure UI adapter tests for the three-mode Persian workspace."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from domain.scenario_contracts import IndicatorProposal, ScenarioType, TargetRankStatus
from engine.scenario_rule_engine import RuleOperation
from engine.ranking_engine import WEIGHTS
from services.selection_scope import SelectionScope
from ui.sensitivity_adapters import (
    action_priority, build_focus_request, build_multi_request, build_target_request,
    count_proposal_presentation, filter_branches, focus_result_presentation, preview_raw_operation,
    rank_change_presentation, result_branch_options, result_sections,
    select_official_branch_result, service_error_message,
    target_solution_comparison, unique_indicator_ids,
)
from ui.sensitivity_labels import (
    OPERATION_LABELS, SCENARIO_TYPE_LABELS, TARGET_STATUS_LABELS,
)
from ui.sensitivity_state import (
    SENSITIVITY_DRAFT_KEY, copy_sensitivity_draft, delete_bulk_rule,
    delete_manual_override, initialize_sensitivity_state, new_scenario_draft,
    reset_sensitivity_draft, return_to_edit, set_focus_branch, set_period,
    set_multi_branch_selection, set_selected_indicators, start_new_scenario,
    switch_scenario_mode,
)


def test_enum_to_persian_labels_are_complete() -> None:
    assert set(SCENARIO_TYPE_LABELS) == set(ScenarioType)
    assert set(OPERATION_LABELS) == {
        RuleOperation.PERCENT_CHANGE, RuleOperation.ABSOLUTE_CHANGE, RuleOperation.SET_VALUE,
    }
    assert TARGET_STATUS_LABELS[TargetRankStatus.TARGET_REACHED] == "رتبه هدف حاصل شد"
    assert all("_" not in label for label in SCENARIO_TYPE_LABELS.values())


@pytest.mark.parametrize(
    ("change", "expected", "tone"),
    [(3, "3 رتبه بهبود", "improvement"), (-2, "2 رتبه افت", "decline"), (0, "بدون تغییر رتبه", "unchanged")],
)
def test_rank_change_presentation(change, expected, tone) -> None:
    assert rank_change_presentation(change) == (expected, tone)


def test_scenario_draft_reset_and_mode_switch_cleanup() -> None:
    state = {}
    initialize_sensitivity_state(state)
    draft = switch_scenario_mode(state, ScenarioType.FOCUS_BRANCH_ONLY)
    draft["focus_branch_id"] = "103"
    draft["focus_changes"] = {"avg_deposits": {"value": 10}}
    switched = switch_scenario_mode(state, ScenarioType.MULTI_BRANCH)
    assert switched["scenario_type"] is ScenarioType.MULTI_BRANCH
    assert switched["focus_branch_id"] is None
    assert switched["focus_changes"] == {}
    switched["bulk_rules"] = [{"x": 1}]
    reset_sensitivity_draft(state)
    assert state[SENSITIVITY_DRAFT_KEY] == new_scenario_draft(ScenarioType.MULTI_BRANCH)


def test_starting_new_focus_scenario_never_restores_old_branch_or_widgets() -> None:
    state = {SENSITIVITY_DRAFT_KEY: new_scenario_draft(ScenarioType.FOCUS_BRANCH_ONLY),
             "sensitivity_focus_branch": "2001", "focus_value_avg_deposits_PERCENT_CHANGE": "10"}
    state[SENSITIVITY_DRAFT_KEY].update(focus_branch_id="2001", current_step=4, entry_source="saved")
    draft = start_new_scenario(state, ScenarioType.FOCUS_BRANCH_ONLY)
    assert draft == new_scenario_draft(ScenarioType.FOCUS_BRANCH_ONLY)
    assert "sensitivity_focus_branch" not in state
    assert not any(str(key).startswith("focus_value_") for key in state)


def test_focus_branch_change_clears_stale_branch_inputs() -> None:
    draft = new_scenario_draft(ScenarioType.FOCUS_BRANCH_ONLY)
    set_focus_branch(draft, "103", "USER_SELECTED_BRANCH")
    draft["selected_indicator_ids"] = ["avg_deposits"]
    draft["focus_changes"] = {"avg_deposits": {"value": 10}}
    set_focus_branch(draft, "101", "USER_SELECTED_BRANCH")
    assert draft["focus_branch_id"] == "101"
    assert draft["selected_indicator_ids"] == []
    assert draft["focus_changes"] == {}


def test_multi_branch_selection_keeps_multiple_branches_and_first_focus() -> None:
    draft = new_scenario_draft(ScenarioType.MULTI_BRANCH)
    set_multi_branch_selection(draft, ["103", "101", "103"], focus_source="USER_SELECTED_BRANCH")
    assert draft["selected_branch_ids"] == ["103", "101"]
    assert draft["focus_branch_id"] == "103"


def test_period_change_clears_request_inputs_but_preserves_mode() -> None:
    draft = new_scenario_draft(ScenarioType.MULTI_BRANCH)
    draft.update(focus_branch_id="103", bulk_rules=[{"x": 1}], execution_result=object())
    set_period(draft, "1404-05")
    assert draft == {**new_scenario_draft(ScenarioType.MULTI_BRANCH), "period": "1404-05"}


def test_indicator_deselection_removes_change_and_backend_results() -> None:
    draft = new_scenario_draft(ScenarioType.FOCUS_BRANCH_ONLY)
    draft.update(selected_indicator_ids=["avg_deposits", "avg_loans"],
                 focus_changes={"avg_deposits": {"value": 1}, "avg_loans": {"value": 2}},
                 execution_result=object(), show_result=True)
    set_selected_indicators(draft, ["avg_loans"])
    assert draft["focus_changes"] == {"avg_loans": {"value": 2}}
    assert draft["execution_result"] is None and not draft["show_result"]


def test_rule_override_deletion_and_return_to_edit_invalidate_results() -> None:
    draft = new_scenario_draft(ScenarioType.MULTI_BRANCH)
    draft.update(bulk_rules=[{"id": 1}], manual_overrides=[{"id": 2}],
                 execution_result=object(), target_solution=object(), show_result=True)
    delete_bulk_rule(draft, 0)
    draft.update(execution_result=object(), target_solution=object(), show_result=True)
    delete_manual_override(draft, 0)
    assert not draft["bulk_rules"] and not draft["manual_overrides"]
    assert draft["execution_result"] is None and draft["target_solution"] is None
    draft.update(execution_result=object(), show_result=True)
    return_to_edit(draft)
    assert draft["execution_result"] is None and not draft["show_result"]


def test_copy_and_new_scenario_never_carry_backend_results() -> None:
    state = {SENSITIVITY_DRAFT_KEY: new_scenario_draft(ScenarioType.FOCUS_BRANCH_ONLY)}
    state[SENSITIVITY_DRAFT_KEY].update(execution_result=object(), target_solution=object(), show_result=True)
    copied = copy_sensitivity_draft(state)
    assert copied["execution_result"] is None and copied["target_solution"] is None and not copied["show_result"]
    reset_sensitivity_draft(state)
    assert state[SENSITIVITY_DRAFT_KEY] == new_scenario_draft(ScenarioType.FOCUS_BRANCH_ONLY)


def test_branch_search_filters_real_name_or_code() -> None:
    frame = pd.DataFrame({"branch_id": ["103", "2001"], "branch_name": ["فاطمی", "خیابان امام زنجان"]})
    assert filter_branches(frame, "103")["branch_id"].tolist() == ["103"]
    assert filter_branches(frame, "زنجان")["branch_id"].tolist() == ["2001"]
    assert len(filter_branches(frame, "")) == 2


def test_indicator_selection_deduplication() -> None:
    assert unique_indicator_ids(["avg_deposits", "loan_count"]) == ("avg_deposits", "loan_count")
    with pytest.raises(ValueError, match="یک‌بار"):
        unique_indicator_ids(["avg_deposits", "avg_deposits"])


def test_operation_preview_and_profit_loss_policy() -> None:
    assert preview_raw_operation(100, RuleOperation.PERCENT_CHANGE, 10, "avg_deposits") == pytest.approx(110)
    assert preview_raw_operation(100, RuleOperation.ABSOLUTE_CHANGE, -5, "avg_deposits") == 95
    assert preview_raw_operation(100, RuleOperation.SET_VALUE, 12, "avg_deposits") == 12
    assert preview_raw_operation(-100, RuleOperation.PERCENT_CHANGE, -10, "profit_loss") == -90
    with pytest.raises(ValueError, match="منفی"):
        preview_raw_operation(10, RuleOperation.ABSOLUTE_CHANGE, -20, "loan_count")


@pytest.mark.parametrize(
    ("base", "operation", "entered", "expected"),
    [
        (4_000_000_000_000.0, RuleOperation.PERCENT_CHANGE, 12.5, 4_500_000_000_000.0),
        (100.0, RuleOperation.PERCENT_CHANGE, -12.5, 87.5),
        (100.0, RuleOperation.PERCENT_CHANGE, 0.0, 100.0),
        (4_000_000_000_000.0, RuleOperation.ABSOLUTE_CHANGE, 0.25, 4_000_000_000_000.25),
        (100.0, RuleOperation.ABSOLUTE_CHANGE, -20.5, 79.5),
        (100.0, RuleOperation.SET_VALUE, 0.0, 0.0),
        (-100.0, RuleOperation.SET_VALUE, -25.5, -25.5),
    ],
)
def test_all_focus_change_modes_cover_signed_zero_decimal_and_large_values(base, operation, entered, expected) -> None:
    indicator = "profit_loss" if expected < 0 else "avg_deposits"
    assert preview_raw_operation(base, operation, entered, indicator) == pytest.approx(expected)


def test_focus_result_presentation_contains_complete_official_baseline_and_scenario() -> None:
    comparison = SimpleNamespace(
        baseline_rank=20, scenario_rank=5, rank_change=15,
        baseline_final_score=600.0, scenario_final_score=625.5, score_change=25.5,
        baseline_grade="Grade 2", scenario_grade="Grade 1",
        indicator_comparisons=({
            "indicator_key": "avg_deposits", "baseline_raw_value": 4_000_000_000_000.0,
            "scenario_raw_value": 4_500_000_000_000.0, "raw_value_change": 500_000_000_000.0,
            "raw_value_change_pct": 12.5, "baseline_score": 500.0, "scenario_score": 550.0,
            "baseline_indicator_rank": 45, "scenario_indicator_rank": 31,
            "indicator_rank_change": 14,
        },),
    )
    summaries, indicators = focus_result_presentation(comparison)
    assert {item["label"] for item in summaries} == {"رتبه کل شعبه", "امتیاز کل", "درجه شعبه"}
    assert next(item for item in summaries if item["label"] == "رتبه کل شعبه")["change"] == "15 رتبه بهبود"
    assert indicators[0]["raw"]["current"] == "4.0 تریلیون"
    assert indicators[0]["raw"]["current_exact"] == "4,000,000,000,000"
    assert indicators[0]["normalized"]["current"] == "500.0 از 1000"
    assert indicators[0]["rank"] == {
        "current": "45", "scenario": "31", "change": "14 رتبه بهبود", "change_numeric": 14,
    }
    assert indicators[0]["weighted"]["current_numeric"] == pytest.approx(500.0 * WEIGHTS["avg_deposits"])
    assert indicators[0]["weighted"]["scenario_numeric"] == pytest.approx(550.0 * WEIGHTS["avg_deposits"])
    assert indicators[0]["weighted"]["effect_numeric"] == pytest.approx(50.0 * WEIGHTS["avg_deposits"])


def test_request_construction_for_all_three_modes() -> None:
    focus = new_scenario_draft(ScenarioType.FOCUS_BRANCH_ONLY)
    focus.update(focus_branch_id="103", scenario_name="آزمون", selected_indicator_ids=["avg_deposits"])
    focus["focus_changes"] = {"avg_deposits": {"operation": "PERCENT_CHANGE", "value": 10}}
    assert build_focus_request(focus).focus_branch_changes[0].operation is RuleOperation.PERCENT_CHANGE

    multi = new_scenario_draft(ScenarioType.MULTI_BRANCH)
    multi.update(focus_branch_id="103", scenario_name="چند شعبه")
    multi["bulk_rules"] = [{"indicator_id": "loan_count", "operation": "ABSOLUTE_CHANGE", "value": 2,
                             "target_scope": "SELECTED_BRANCHES", "selected_branch_ids": ["103", "101"]}]
    multi["manual_overrides"] = [{"branch_id": "103", "indicator_id": "loan_count", "operation": "SET_VALUE", "value": 50}]
    request = build_multi_request(multi)
    assert request.bulk_rules[0].target_scope is SelectionScope.SELECTED_BRANCHES
    assert request.manual_overrides[0].operation is RuleOperation.SET_VALUE

    target = new_scenario_draft(ScenarioType.TARGET_RANK)
    target.update(focus_branch_id="103", selected_indicator_ids=["profit_loss"])
    target["target_rank_request"] = {"target_rank": 20, "max_growth_percent": 50}
    target_request = build_target_request(target)
    assert target_request.allow_profit_loss
    assert target_request.max_iterations == 40


def test_invalid_mixed_mode_is_blocked_before_service_call() -> None:
    draft = new_scenario_draft(ScenarioType.MULTI_BRANCH)
    draft.update(focus_branch_id="103", selected_indicator_ids=["avg_deposits"])
    draft["focus_changes"] = {"avg_deposits": {"operation": "SET_VALUE", "value": 1}}
    with pytest.raises(ValueError, match="سازگار نیست"):
        build_focus_request(draft)


def test_modified_and_rank_affected_sections_remain_separate() -> None:
    modified = (SimpleNamespace(branch_id="103"),)
    affected = (SimpleNamespace(branch_id="103"), SimpleNamespace(branch_id="101"))
    assert result_sections(SimpleNamespace(modified_branches=modified, rank_affected_branches=affected)) == {
        "modified_branches": modified, "rank_affected_branches": affected,
    }


def test_result_branch_navigation_is_focus_first_and_uses_official_objects() -> None:
    focus = SimpleNamespace(branch_id="103", indicator_comparisons=({"x": 1},))
    modified = SimpleNamespace(branch_id="101", indicator_comparisons=({"x": 2},))
    affected = SimpleNamespace(branch_id="202", indicator_comparisons=())
    result = SimpleNamespace(
        request=SimpleNamespace(focus_branch_id="103"), focus_branch_comparison=focus,
        modified_branches=(focus, modified), rank_affected_branches=(modified, affected),
    )
    assert result_branch_options(result) == ("103", "101", "202")
    assert select_official_branch_result(result, "103") is focus
    assert select_official_branch_result(result, "101") is modified
    assert select_official_branch_result(result, "202") is affected
    assert affected.indicator_comparisons == ()


def _proposal(indicator: str, before: float, after: float, *, count: bool = False, candidate: float = 10.2):
    return IndicatorProposal(indicator, 10, candidate, 11 if count else 12, count, 1, 10,
                             baseline_weighted_contribution=before,
                             scenario_weighted_contribution=after)


def test_count_proposal_presentation_uses_verified_integer() -> None:
    shown = count_proposal_presentation(_proposal("deposit_count", 1, 2, count=True))
    assert shown == {"applicable_value": 11, "numeric_candidate": 10.2, "show_ceiling_note": True}


def test_action_priority_uses_only_official_weighted_contribution_delta() -> None:
    proposals = [_proposal("avg_loans", 2, 2.2), _proposal("avg_deposits", 1, 1.8)]
    rows, tied = action_priority(proposals)
    assert [row["indicator_id"] for row in rows] == ["avg_deposits", "avg_loans"]
    assert rows[0]["weighted_contribution_delta"] == pytest.approx(0.8)
    assert not tied


def test_action_priority_reports_nearly_identical_deltas() -> None:
    rows, tied = action_priority([_proposal("avg_loans", 1, 1.5), _proposal("avg_deposits", 2, 2.5)])
    assert [row["indicator_id"] for row in rows] == ["avg_deposits", "avg_loans"]
    assert len(rows) == 2 and tied


def test_target_full_comparison_uses_official_solver_outputs(monkeypatch) -> None:
    expected = pd.DataFrame({"official_backend_value": [42]})
    captured = {}

    def fake_compare(baseline_outputs, scenario_outputs):
        captured.update(baseline=baseline_outputs, scenario=scenario_outputs)
        return SimpleNamespace(branch_comparison=expected)

    monkeypatch.setattr("engine.comparison_engine.compare_model_outputs", fake_compare)
    solution = SimpleNamespace(baseline_outputs=object(), scenario_outputs=object())
    shown = target_solution_comparison(solution)
    assert shown is expected
    assert captured == {"baseline": solution.baseline_outputs, "scenario": solution.scenario_outputs}


def test_overlap_error_is_persian_and_hides_internal_indicator_key() -> None:
    message = service_error_message("V1 forbids overlapping bulk rules for the same branch-indicator pair (103, avg_deposits)")
    assert "103" in message and "میانگین سپرده‌ها" in message
    assert "avg_deposits" not in message
