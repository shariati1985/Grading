"""Bulk-rule, override precedence, and structured validation tests."""

from __future__ import annotations

from copy import deepcopy
import math

import pandas as pd
import pytest

from engine.indicator_registry import INDICATOR_REGISTRY, PROFIT_LOSS_KEY
from engine.scenario_rule_engine import (
    IndicatorRule,
    ManualOverride,
    RuleOperation,
    ScenarioRuleEngine,
    ScenarioRuleValidationError,
)
from services.selection_scope import SelectionResolver, SelectionScope
from services.user_context import CurrentUser


@pytest.fixture
def baseline() -> pd.DataFrame:
    values = {key: [100.0, 30.0] for key in INDICATOR_REGISTRY}
    values[PROFIT_LOSS_KEY] = [-100.0, 100.0]
    return pd.DataFrame(
        {"branch_id": ["101", "202"], "branch_name": ["یک", "دو"], "region": ["الف", "ب"], **values}
    )


def rule(key: str, operation: RuleOperation, value: float) -> IndicatorRule:
    return IndicatorRule(key, operation, value)


def final(preview, branch_id: str, key: str) -> float:
    return float(next(row.final_value for row in preview.rows if row.branch_id == branch_id and row.indicator_key == key))


@pytest.mark.parametrize(
    ("operation", "value", "expected"),
    [
        (RuleOperation.PERCENT_CHANGE, 10, 110),
        (RuleOperation.PERCENT_CHANGE, -50, 50),
        (RuleOperation.PERCENT_CHANGE, -100, 0),
        (RuleOperation.ABSOLUTE_CHANGE, 20, 120),
        (RuleOperation.ABSOLUTE_CHANGE, -20, 80),
        (RuleOperation.ABSOLUTE_CHANGE, -100, 0),
        (RuleOperation.SET_VALUE, 25, 25),
        (RuleOperation.SET_VALUE, 0, 0),
    ],
)
def test_valid_operations(baseline, operation, value, expected) -> None:
    preview = ScenarioRuleEngine.preview(["101"], baseline, [rule("deposit_count", operation, value)])
    assert preview.is_valid
    assert final(preview, "101", "deposit_count") == pytest.approx(expected)


@pytest.mark.parametrize("key", [key for key in INDICATOR_REGISTRY if key != PROFIT_LOSS_KEY])
def test_all_seven_non_profit_indicators_reject_negative_set_value(baseline, key) -> None:
    preview = ScenarioRuleEngine.preview(["101"], baseline, [rule(key, RuleOperation.SET_VALUE, -1)])
    assert not preview.is_valid
    assert preview.issues[0].code == "BELOW_MINIMUM"
    assert preview.issues[0].calculated_value == -1


def test_bulk_rule_reports_only_branches_that_become_negative(baseline) -> None:
    preview = ScenarioRuleEngine.preview(
        ["101", "202"], baseline, [rule("loan_count", RuleOperation.ABSOLUTE_CHANGE, -50)]
    )
    assert preview.invalid_change_count == 1
    assert preview.issues[0].branch_id == "202"
    assert preview.issues[0].baseline_value == 30
    assert preview.issues[0].input_value == -50
    with pytest.raises(ScenarioRuleValidationError):
        ScenarioRuleEngine.generate_changes(
            ["101", "202"], baseline, [rule("loan_count", RuleOperation.ABSOLUTE_CHANGE, -50)]
        )


def test_profit_loss_uses_mathematical_percentage_and_allows_any_finite_sign(baseline) -> None:
    percent = ScenarioRuleEngine.preview(
        ["101"], baseline, [rule(PROFIT_LOSS_KEY, RuleOperation.PERCENT_CHANGE, 20)]
    )
    assert final(percent, "101", PROFIT_LOSS_KEY) == -120
    for value in (-500, 0, 500):
        preview = ScenarioRuleEngine.preview(
            ["101"], baseline, [rule(PROFIT_LOSS_KEY, RuleOperation.SET_VALUE, value)]
        )
        assert preview.is_valid
        assert final(preview, "101", PROFIT_LOSS_KEY) == value


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_inputs_are_rejected_structurally(baseline, value) -> None:
    preview = ScenarioRuleEngine.preview(
        ["101"], baseline, [rule("avg_loans", RuleOperation.SET_VALUE, value)]
    )
    assert not preview.is_valid
    assert preview.issues[0].code == "INVALID_INPUT"


def test_independent_rules_and_unchanged_indicators(baseline) -> None:
    rules = [
        rule("deposit_count", RuleOperation.PERCENT_CHANGE, 10),
        rule("avg_loans", RuleOperation.SET_VALUE, 75),
    ]
    preview = ScenarioRuleEngine.preview(["101"], baseline, rules)
    assert preview.active_bulk_rule_count == 2
    assert preview.unchanged_indicator_count == 6
    assert final(preview, "101", "loan_count") == 100
    assert {change.indicator_key for change in preview.changes} == {"deposit_count", "avg_loans"}


def test_rules_for_all_eight_indicators(baseline) -> None:
    rules = [rule(key, RuleOperation.ABSOLUTE_CHANGE, 1) for key in INDICATOR_REGISTRY]
    preview = ScenarioRuleEngine.preview(["101"], baseline, rules)
    assert preview.active_bulk_rule_count == 8
    assert preview.unchanged_indicator_count == 0
    assert preview.generated_change_count == 8


def test_manual_override_precedence_is_indicator_and_branch_specific(baseline) -> None:
    rules = [
        rule("deposit_count", RuleOperation.PERCENT_CHANGE, 10),
        rule("loan_count", RuleOperation.ABSOLUTE_CHANGE, 5),
    ]
    overrides = [ManualOverride("101", "deposit_count", RuleOperation.SET_VALUE, 999)]
    preview = ScenarioRuleEngine.preview(["101", "202"], baseline, rules, overrides)
    assert final(preview, "101", "deposit_count") == 999
    assert final(preview, "101", "loan_count") == 105
    assert final(preview, "202", "deposit_count") == 33
    source = next(row.change_source for row in preview.rows if row.branch_id == "101" and row.indicator_key == "deposit_count")
    assert source == "manual_override"


def test_valid_negative_profit_override_and_invalid_other_override(baseline) -> None:
    valid = ScenarioRuleEngine.preview(
        ["101"], baseline, [], [ManualOverride("101", PROFIT_LOSS_KEY, RuleOperation.SET_VALUE, -900)]
    )
    assert valid.is_valid
    invalid = ScenarioRuleEngine.preview(
        ["101"], baseline, [], [ManualOverride("101", "avg_deposits", RuleOperation.SET_VALUE, -1)]
    )
    assert not invalid.is_valid


def test_duplicate_rules_and_overrides_are_rejected(baseline) -> None:
    duplicate_rules = [rule("loan_count", RuleOperation.SET_VALUE, 1), rule("loan_count", RuleOperation.SET_VALUE, 2)]
    assert ScenarioRuleEngine.preview(["101"], baseline, duplicate_rules).issues[0].code == "DUPLICATE_RULE"
    duplicate_overrides = [
        ManualOverride("101", "loan_count", RuleOperation.SET_VALUE, 1),
        ManualOverride("101", "loan_count", RuleOperation.SET_VALUE, 2),
    ]
    assert ScenarioRuleEngine.preview(["101"], baseline, [], duplicate_overrides).issues[0].code == "DUPLICATE_OVERRIDE"


def test_missing_baseline_is_rejected_even_for_set_value_and_source_is_unchanged(baseline) -> None:
    original = deepcopy(baseline)
    baseline.loc[0, "avg_commitments"] = math.nan
    preview = ScenarioRuleEngine.preview(
        ["101"], baseline, [rule("avg_commitments", RuleOperation.SET_VALUE, 10)]
    )
    assert preview.issues[0].code == "INVALID_BASELINE"
    pd.testing.assert_frame_equal(baseline, original.assign(avg_commitments=[math.nan, 30.0]))


def test_output_order_follows_branch_order_then_registry_order(baseline) -> None:
    preview = ScenarioRuleEngine.preview(["202", "101", "202"], baseline, [])
    assert [(row.branch_id, row.indicator_key) for row in preview.rows] == [
        (branch_id, key) for branch_id in ("202", "101") for key in INDICATOR_REGISTRY
    ]


@pytest.mark.parametrize(
    ("scope", "kwargs", "expected"),
    [
        (SelectionScope.USER_BRANCH, {}, ["101"]),
        (SelectionScope.SELECTED_BRANCHES, {"selected_branch_ids": ["202"]}, ["202"]),
        (SelectionScope.SELECTED_REGIONS, {"selected_regions": ["الف"]}, ["101"]),
        (SelectionScope.ALL_BRANCHES, {}, ["101", "202"]),
    ],
)
def test_rules_apply_to_every_existing_selection_scope(
    baseline, scope, kwargs, expected
) -> None:
    current_user = CurrentUser("user", "کاربر", (), branch_id="101")
    selected = SelectionResolver.resolve(scope, baseline, current_user, **kwargs)
    preview = ScenarioRuleEngine.preview(
        selected, baseline, [rule("deposit_count", RuleOperation.ABSOLUTE_CHANGE, 1)]
    )
    assert preview.is_valid
    assert [change.branch_id for change in preview.changes] == expected


def test_user_branch_is_not_controlled_by_network_bulk_rule(baseline) -> None:
    user_branch = "101"
    other_branches = ["202"]
    network = ScenarioRuleEngine.preview(
        other_branches,
        baseline,
        [rule("deposit_count", RuleOperation.SET_VALUE, 500)],
    )
    user = ScenarioRuleEngine.preview(
        [user_branch],
        baseline,
        [],
        [ManualOverride(user_branch, "deposit_count", RuleOperation.SET_VALUE, 250)],
    )
    assert [(item.branch_id, item.scenario_value) for item in user.changes] == [
        ("101", 250)
    ]
    assert [(item.branch_id, item.scenario_value) for item in network.changes] == [
        ("202", 500)
    ]


def test_user_branch_no_change_remains_baseline_while_network_rule_applies(baseline) -> None:
    user = ScenarioRuleEngine.preview(["101"], baseline, [], [])
    network = ScenarioRuleEngine.preview(
        ["202"], baseline, [rule("loan_count", RuleOperation.ABSOLUTE_CHANGE, 10)]
    )
    assert user.changes == []
    assert {item.branch_id for item in network.changes} == {"202"}


@pytest.mark.parametrize(
    ("operation", "value", "expected"),
    [
        (RuleOperation.PERCENT_CHANGE, 25, 125),
        (RuleOperation.PERCENT_CHANGE, -25, 75),
        (RuleOperation.ABSOLUTE_CHANGE, 20, 120),
        (RuleOperation.ABSOLUTE_CHANGE, -20, 80),
        (RuleOperation.SET_VALUE, 333, 333),
    ],
)
def test_focus_override_operations_are_applied_with_signed_values(
    baseline, operation, value, expected
) -> None:
    preview = ScenarioRuleEngine.preview(
        ["101"], baseline, [],
        [ManualOverride("101", "deposit_count", operation, value, "focus_branch_override")],
    )
    change = next(item for item in preview.changes if item.indicator_key == "deposit_count")
    assert change.scenario_value == expected
    row = next(item for item in preview.rows if item.indicator_key == "deposit_count")
    assert row.change_source == "focus_branch_override"


def test_focus_and_exception_multiple_indicators_and_branches_are_independent(baseline) -> None:
    focus = ScenarioRuleEngine.preview(
        ["101"], baseline, [],
        [
            ManualOverride("101", "deposit_count", RuleOperation.PERCENT_CHANGE, 10, "focus_branch_override"),
            ManualOverride("101", "loan_count", RuleOperation.SET_VALUE, 321, "focus_branch_override"),
        ],
    )
    network = ScenarioRuleEngine.preview(
        ["202"], baseline,
        [IndicatorRule("deposit_count", RuleOperation.PERCENT_CHANGE, 5)],
        [
            ManualOverride("202", "deposit_count", RuleOperation.PERCENT_CHANGE, -20, "branch_exception"),
            ManualOverride("202", "loan_count", RuleOperation.ABSOLUTE_CHANGE, -10, "branch_exception"),
        ],
    )
    focus_values = {item.indicator_key: item.scenario_value for item in focus.changes}
    network_values = {item.indicator_key: item.scenario_value for item in network.changes}
    assert focus_values == pytest.approx({"deposit_count": 110, "loan_count": 321})
    assert network_values == pytest.approx({"deposit_count": 24, "loan_count": 20})


def test_exception_beats_network_only_for_matching_indicator(baseline) -> None:
    preview = ScenarioRuleEngine.preview(
        ["202"], baseline,
        [
            IndicatorRule("deposit_count", RuleOperation.PERCENT_CHANGE, 10),
            IndicatorRule("loan_count", RuleOperation.PERCENT_CHANGE, 10),
        ],
        [ManualOverride("202", "deposit_count", RuleOperation.SET_VALUE, 7, "branch_exception")],
    )
    rows = {row.indicator_key: row for row in preview.rows}
    assert rows["deposit_count"].final_value == 7
    assert rows["deposit_count"].change_source == "branch_exception"
    assert rows["loan_count"].final_value == pytest.approx(33)
    assert rows["loan_count"].change_source == "bulk_rule"
