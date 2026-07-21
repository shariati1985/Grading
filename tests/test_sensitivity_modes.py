"""Backend/domain tests for the three explicit sensitivity modes."""

from __future__ import annotations

import pandas as pd
import pytest

from domain.scenario_contracts import (
    BulkRule, IndicatorChange, ScenarioRequest, ScenarioType,
    TargetRankRequest, TargetRankStatus,
)
from engine.ranking_engine import BRANCH_ID, INDICATOR_KEYS, run_ranking_model
from engine.scenario_rule_engine import ManualOverride, RuleOperation
from services.scenario_execution_service import ScenarioExecutionService
from services.scenario_execution_service import ScenarioRequestValidationError
from services.selection_scope import SelectionScope
from services.target_rank_solver import solve_target_rank


def _request(mode: ScenarioType, focus: str, **kwargs) -> ScenarioRequest:
    return ScenarioRequest(mode, "test", focus, **kwargs)


def test_focus_only_changes_multiple_indicators_and_no_other_raw_rows(input_df) -> None:
    baseline = input_df.copy(deep=True)
    focus = str(input_df.iloc[0][BRANCH_ID])
    request = _request(
        ScenarioType.FOCUS_BRANCH_ONLY, focus,
        focus_branch_changes=(
            IndicatorChange("avg_deposits", RuleOperation.PERCENT_CHANGE, 10),
            IndicatorChange("loan_count", RuleOperation.ABSOLUTE_CHANGE, 5),
        ),
    )
    result = ScenarioExecutionService().execute(request, input_df)
    pd.testing.assert_frame_equal(input_df, baseline)
    unchanged = result.scenario_data.loc[~result.scenario_data[BRANCH_ID].eq(focus)]
    expected = result.baseline_data.loc[~result.baseline_data[BRANCH_ID].eq(focus)]
    pd.testing.assert_frame_equal(unchanged.reset_index(drop=True), expected.reset_index(drop=True))
    assert {change.indicator_key for change in result.changes} == {"avg_deposits", "loan_count"}
    assert len(result.scenario_outputs.final_result) == len(input_df)


@pytest.mark.parametrize(
    ("scope", "scope_kwargs"),
    [
        (SelectionScope.USER_BRANCH, {}),
        (SelectionScope.SELECTED_BRANCHES, {"selected_branch_ids": ("103", "101")}),
        (SelectionScope.SELECTED_REGIONS, {"selected_regions": ("تهران مرکز",)}),
        (SelectionScope.ALL_BRANCHES, {}),
    ],
)
def test_multi_branch_bulk_scopes_apply_only_to_resolved_branches(
    input_df, scope, scope_kwargs
) -> None:
    baseline = input_df.copy(deep=True)
    rule = BulkRule(
        "deposit_count", RuleOperation.ABSOLUTE_CHANGE, 1, scope, **scope_kwargs
    )
    result = ScenarioExecutionService().execute(
        _request(ScenarioType.MULTI_BRANCH, "103", bulk_rules=(rule,)), input_df
    )
    changed = set(result.scenario_data.loc[
        result.scenario_data["deposit_count"].ne(result.baseline_data["deposit_count"]), BRANCH_ID
    ])
    assert changed == {change.branch_id for change in result.changes}
    assert changed
    pd.testing.assert_frame_equal(input_df, baseline)


def test_multi_manual_overrides_win_and_can_differ_by_branch(input_df) -> None:
    rule = BulkRule(
        "deposit_count", RuleOperation.SET_VALUE, 500,
        SelectionScope.SELECTED_BRANCHES, ("103", "101", "102"),
    )
    overrides = (
        ManualOverride("103", "deposit_count", RuleOperation.SET_VALUE, 700),
        ManualOverride("101", "deposit_count", RuleOperation.SET_VALUE, 800),
    )
    result = ScenarioExecutionService().execute(
        _request(ScenarioType.MULTI_BRANCH, "103", bulk_rules=(rule,), manual_overrides=overrides),
        input_df,
    )
    values = result.scenario_data.set_index(BRANCH_ID)["deposit_count"]
    assert values["103"] == 700
    assert values["101"] == 800
    assert values["102"] == 500
    assert {item.branch_id for item in result.modified_branches} == {"103", "101", "102"}


def test_modified_and_rank_affected_branches_are_distinct(input_df) -> None:
    result = ScenarioExecutionService().execute(
        _request(
            ScenarioType.FOCUS_BRANCH_ONLY, "103",
            focus_branch_changes=(
                IndicatorChange("avg_deposits", RuleOperation.PERCENT_CHANGE, 100),
            ),
        ), input_df,
    )
    assert [item.branch_id for item in result.modified_branches] == ["103"]
    assert len(result.rank_affected_branches) > 1
    for item in (
        result.focus_branch_comparison,
        *result.modified_branches,
        *result.rank_affected_branches,
    ):
        assert item.rank_change == item.baseline_rank - item.scenario_rank


@pytest.mark.parametrize(
    "rules",
    [
        (
            BulkRule("avg_deposits", RuleOperation.PERCENT_CHANGE, 5,
                     SelectionScope.SELECTED_BRANCHES, ("103",)),
            BulkRule("avg_deposits", RuleOperation.PERCENT_CHANGE, 3,
                     SelectionScope.SELECTED_BRANCHES, ("103",)),
        ),
        (
            BulkRule("avg_deposits", RuleOperation.PERCENT_CHANGE, 5,
                     SelectionScope.ALL_BRANCHES),
            BulkRule("avg_deposits", RuleOperation.PERCENT_CHANGE, 3,
                     SelectionScope.SELECTED_REGIONS, selected_regions=("تهران مرکز",)),
        ),
        (
            BulkRule("avg_deposits", RuleOperation.NO_CHANGE, 0,
                     SelectionScope.SELECTED_BRANCHES, ("103",)),
            BulkRule("avg_deposits", RuleOperation.PERCENT_CHANGE, 3,
                     SelectionScope.SELECTED_BRANCHES, ("103",)),
        ),
    ],
)
def test_overlapping_bulk_rules_are_rejected_before_ranking(input_df, rules, monkeypatch) -> None:
    def ranking_must_not_run(_):
        raise AssertionError("ranking must not run for invalid overlap")

    monkeypatch.setattr("services.scenario_execution_service.run_ranking_model", ranking_must_not_run)
    with pytest.raises(ScenarioRequestValidationError, match="overlapping bulk rules"):
        ScenarioExecutionService().execute(
            _request(ScenarioType.MULTI_BRANCH, "103", bulk_rules=rules), input_df
        )


def test_focus_noop_is_not_marked_modified(input_df) -> None:
    current = float(input_df.loc[input_df[BRANCH_ID].astype(str).eq("103"), "loan_count"].iloc[0])
    result = ScenarioExecutionService().execute(
        _request(
            ScenarioType.FOCUS_BRANCH_ONLY, "103",
            focus_branch_changes=(
                IndicatorChange("loan_count", RuleOperation.SET_VALUE, current),
            ),
        ), input_df,
    )
    assert result.modified_branches == ()
    assert result.rank_affected_branches == ()


def _target(input_df, **changes) -> TargetRankRequest:
    defaults = dict(
        focus_branch_id="103", target_rank=29,
        selected_indicator_ids=("avg_deposits", "avg_loans", "avg_commitments"),
        max_growth_percent=1000.0, tolerance_percent=0.001,
        search_precision_percent=0.001, max_iterations=40,
    )
    defaults.update(changes)
    return TargetRankRequest(**defaults)


def test_target_rank_no_change_invalid_and_unreachable(input_df) -> None:
    assert solve_target_rank(_target(input_df, target_rank=30), input_df).status is TargetRankStatus.NO_CHANGE_REQUIRED
    assert solve_target_rank(_target(input_df, target_rank=0), input_df).status is TargetRankStatus.INVALID_REQUEST
    unreachable = solve_target_rank(
        _target(input_df, focus_branch_id="2621", target_rank=1, max_growth_percent=1), input_df
    )
    assert unreachable.status is TargetRankStatus.TARGET_NOT_REACHABLE
    assert not unreachable.target_reached


def test_target_solver_is_deterministic_minimal_and_preserves_raw_population(input_df) -> None:
    original = input_df.copy(deep=True)
    request = _target(input_df)
    first = solve_target_rank(request, input_df)
    second = solve_target_rank(request, input_df)
    assert first.status is TargetRankStatus.TARGET_REACHED
    assert first.achieved_rank <= request.target_rank
    assert first.required_common_growth_percent == second.required_common_growth_percent
    assert first.iterations == second.iterations <= request.max_iterations
    pd.testing.assert_frame_equal(input_df, original)
    non_focus = ~first.scenario_data[BRANCH_ID].eq("103")
    pd.testing.assert_frame_equal(
        first.scenario_data.loc[non_focus].reset_index(drop=True),
        first.baseline_outputs.raw_data.loc[non_focus].reset_index(drop=True),
    )
    unselected = set(INDICATOR_KEYS) - set(request.selected_indicator_ids)
    before = first.baseline_outputs.raw_data.set_index(BRANCH_ID).loc["103"]
    after = first.scenario_data.set_index(BRANCH_ID).loc["103"]
    assert all(after[key] == before[key] for key in unselected)
    assert {round(item.percent_change, 9) for item in first.indicator_proposals} == {
        round(first.required_common_growth_percent, 9)
    }


def test_target_profit_loss_improves_negative_toward_zero(input_df) -> None:
    solution = solve_target_rank(
        _target(
            input_df, selected_indicator_ids=("profit_loss",), allow_profit_loss=True,
            max_growth_percent=10, target_rank=1,
        ), input_df,
    )
    proposal = solution.indicator_proposals[0]
    assert proposal.baseline_raw_value < 0
    assert proposal.proposed_raw_value > proposal.baseline_raw_value
    assert proposal.proposed_raw_value == pytest.approx(proposal.baseline_raw_value * 0.9)


def test_target_profit_loss_positive_increases_and_zero_stays_zero(input_df) -> None:
    positive_id = str(input_df.loc[input_df["profit_loss"].gt(0), BRANCH_ID].iloc[-1])
    positive = solve_target_rank(
        _target(
            input_df, focus_branch_id=positive_id, selected_indicator_ids=("profit_loss",),
            allow_profit_loss=True, max_growth_percent=10, target_rank=1,
        ), input_df,
    ).indicator_proposals[0]
    assert positive.proposed_raw_value == pytest.approx(positive.baseline_raw_value * 1.1)

    zero_data = input_df.copy(deep=True)
    zero_data.loc[zero_data[BRANCH_ID].eq("103"), "profit_loss"] = 0.0
    zero = solve_target_rank(
        _target(
            zero_data, selected_indicator_ids=("profit_loss",), allow_profit_loss=True,
            max_growth_percent=10, target_rank=1,
        ), zero_data,
    ).indicator_proposals[0]
    assert zero.baseline_raw_value == zero.proposed_raw_value == 0.0
    assert zero.note == (
        "Zero Profit/Loss was unchanged because percentage growth has no non-zero base."
    )


def test_target_count_proposal_uses_named_integer_policy_and_official_recheck(input_df) -> None:
    request = _target(
        input_df, selected_indicator_ids=("deposit_count",),
        max_growth_percent=10, target_rank=1,
    )
    solution = solve_target_rank(request, input_df)
    proposal = solution.indicator_proposals[0]
    assert proposal.is_count_indicator
    assert proposal.proposed_raw_value == int(proposal.proposed_raw_value)
    assert proposal.proposed_raw_value >= proposal.numeric_candidate_raw_value
    rerun = run_ranking_model(solution.scenario_data)
    pd.testing.assert_frame_equal(
        rerun.final_result.reset_index(drop=True),
        solution.scenario_outputs.final_result.reset_index(drop=True),
    )


def test_target_solver_max_iterations_is_respected(input_df) -> None:
    solution = solve_target_rank(_target(input_df, max_iterations=1), input_df)
    assert solution.iterations == 1
    assert solution.status is TargetRankStatus.MAX_ITERATIONS_REACHED
    assert solution.target_reached
    assert not solution.minimum_growth_established
    assert "not achieved before max_iterations" in solution.message


def test_duplicate_target_indicators_are_invalid(input_df) -> None:
    solution = solve_target_rank(
        _target(input_df, selected_indicator_ids=("avg_deposits", "avg_deposits")),
        input_df,
    )
    assert solution.status is TargetRankStatus.INVALID_REQUEST


@pytest.mark.parametrize(
    "scenario_request",
    [
        _request(
            ScenarioType.FOCUS_BRANCH_ONLY, "103",
            target_rank_request=_target(None),
        ),
        _request(
            ScenarioType.FOCUS_BRANCH_ONLY, "103",
            manual_overrides=(
                ManualOverride("101", "loan_count", RuleOperation.SET_VALUE, 1),
            ),
        ),
        _request(
            ScenarioType.MULTI_BRANCH, "103",
            target_rank_request=_target(None),
        ),
        _request(
            ScenarioType.TARGET_RANK, "103",
            target_rank_request=_target(None),
            focus_branch_changes=(
                IndicatorChange("loan_count", RuleOperation.ABSOLUTE_CHANGE, 1),
            ),
        ),
    ],
)
def test_invalid_mixed_mode_requests_fail_before_ranking(
    input_df, scenario_request, monkeypatch
) -> None:
    def ranking_must_not_run(_):
        raise AssertionError("ranking must not run for invalid mixed mode")

    monkeypatch.setattr("services.scenario_execution_service.run_ranking_model", ranking_must_not_run)
    with pytest.raises(ScenarioRequestValidationError):
        ScenarioExecutionService().execute(scenario_request, input_df)


def test_application_service_delegates_target_rank_to_official_solver(monkeypatch, input_df) -> None:
    expected = object()
    request = object()
    captured = {}

    def fake_solver(received_request, received_data):
        captured.update(request=received_request, data=received_data)
        return expected

    monkeypatch.setattr("services.target_rank_solver.solve_target_rank", fake_solver)
    actual = ScenarioExecutionService().solve_target_rank(request, input_df)
    assert actual is expected
    assert captured["request"] is request and captured["data"] is input_df
