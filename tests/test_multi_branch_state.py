import pytest

from domain.scenario_contracts import ScenarioType
from ui.multi_branch_state import (
    MULTI_BRANCH_STAGE_LABELS,
    MULTI_BRANCH_STAGE_ORDER,
    MULTI_BRANCH_STATE_KEY,
    MultiBranchStage,
    consume_scroll_to_top,
    current_multi_branch_stage,
    initialize_multi_branch_state,
    move_to_multi_branch_stage,
    new_multi_branch_workspace,
    reset_multi_branch_state,
)
from ui.sensitivity_state import start_new_scenario
from ui.sensitivity_state import SENSITIVITY_DRAFT_KEY, new_scenario_draft
import pandas as pd

from engine.indicator_registry import INDICATOR_REGISTRY
from ui.multi_branch_page import (
    _build_scenario,
    _exception_indicator_options,
    _exception_rule_review_rows,
    _general_rule_review_rows,
    _has_exception_rule,
    _parse_percentage_input,
    _primary_rule_rows,
    _render_exception_card,
    _render_primary_rule_card,
    _render_review_rule_card,
    get_available_exception_indicator_keys,
)


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


def test_new_multi_branch_workspace_has_no_forced_primary_branch_default() -> None:
    workspace = new_multi_branch_workspace()

    assert workspace["primary_branch_code"] is None


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


def test_stage_navigation_sets_and_consumes_one_shot_scroll_flag() -> None:
    workspace = new_multi_branch_workspace()

    move_to_multi_branch_stage(workspace, MultiBranchStage.GENERAL_RULES)

    assert consume_scroll_to_top(workspace) is True
    assert consume_scroll_to_top(workspace) is False


def test_same_step_state_invalidation_does_not_set_scroll_flag() -> None:
    from ui.multi_branch_state import invalidate_multi_branch_result

    workspace = new_multi_branch_workspace()
    invalidate_multi_branch_result(workspace)

    assert consume_scroll_to_top(workspace) is False


def test_starting_new_multi_branch_scenario_discards_previous_workspace() -> None:
    state = {MULTI_BRANCH_STATE_KEY: {"scenario_name": "قبلی"}}
    start_new_scenario(state, ScenarioType.MULTI_BRANCH)
    assert MULTI_BRANCH_STATE_KEY not in state


def test_percentage_parser_accepts_latin_persian_and_decimal_values() -> None:
    assert _parse_percentage_input("25") == 25.0
    assert _parse_percentage_input("۲۵") == 25.0
    assert _parse_percentage_input("12.5") == 12.5
    assert _parse_percentage_input("۱۲٫۵") == 12.5


@pytest.mark.parametrize("value", ["", "0", "۰", "-1", "abc", "1..2", float("nan"), float("inf")])
def test_percentage_parser_rejects_blank_zero_negative_and_invalid_values(value) -> None:
    with pytest.raises(ValueError):
        _parse_percentage_input(value)


def test_exception_branch_selector_uses_empty_placeholder_and_rejects_submit_without_branch() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "ui" / "multi_branch_page.py").read_text(encoding="utf-8")
    body = source.split("def _exceptions", 1)[1].split("def _primary_overrides", 1)[0]

    assert "[None, *ids]" in body
    assert '"انتخاب شعبه" if item is None' in body
    assert 'key="multi_exception_branch"' in body
    assert 'if branch is None:' in body
    assert 'raise ValueError("شعبه استثنا را انتخاب کنید.")' in body
    assert "exceptions.setdefault(str(branch), [])" in body


def test_deliberately_selected_exception_branch_is_persisted_without_placeholder() -> None:
    from domain.multi_branch_contracts import ActorContext, ActorScope

    workspace = {
        "scenario_name": "سناریو",
        "primary_branch_code": "101",
        "period": "1404-04",
        "general_rules": [],
        "branch_exceptions": {"202": [{"indicator_key": "avg_deposits", "direction": "increase", "percentage": 12.5}]},
        "primary_branch_overrides": {},
    }
    scenario = _build_scenario(workspace, 3, ActorContext("u", ActorScope.STAFF))

    assert [item.branch_code for item in scenario.branch_exceptions] == ["202"]
    assert None not in [item.branch_code for item in scenario.branch_exceptions]


def test_exception_indicator_availability_is_scoped_to_selected_branch() -> None:
    deposit_key = "avg_deposits"
    loan_key = "avg_loans"
    exceptions = {
        "101": [{"indicator_key": deposit_key, "direction": "increase", "percentage": 10.0}]
    }
    all_keys = list(INDICATOR_REGISTRY)

    branch_a_options = get_available_exception_indicator_keys(all_keys, exceptions, "101")
    branch_b_options = get_available_exception_indicator_keys(all_keys, exceptions, "202")

    assert deposit_key not in branch_a_options
    assert loan_key in branch_a_options
    assert deposit_key in branch_b_options
    assert loan_key in branch_b_options


def test_exception_duplicate_validation_is_exact_branch_indicator_pair() -> None:
    key = "avg_loans"
    exceptions = {
        "101": [{"indicator_key": key, "direction": "increase", "percentage": 10.0}]
    }

    assert _has_exception_rule(exceptions, 101, key) is True
    assert _has_exception_rule(exceptions, "202", key) is False


def test_general_rules_do_not_remove_exception_indicator_options() -> None:
    key = "avg_loans"
    workspace = {
        "general_rules": [{"indicator_key": key, "direction": "increase", "percentage": 10.0}],
        "branch_exceptions": {},
    }

    assert key in _exception_indicator_options(workspace["branch_exceptions"], "101")


def test_primary_overrides_do_not_remove_exception_indicator_options() -> None:
    key = "avg_loans"
    workspace = {
        "branch_exceptions": {},
        "primary_branch_overrides": {
            key: {"input_mode": "final", "input_value": 1.0, "resolved_raw_value": 1.0}
        },
    }

    assert key in get_available_exception_indicator_keys(
        list(INDICATOR_REGISTRY), workspace["branch_exceptions"], "101"
    )


def test_no_exceptions_makes_every_canonical_indicator_available() -> None:
    assert get_available_exception_indicator_keys(list(INDICATOR_REGISTRY), {}, "101") == list(INDICATOR_REGISTRY)


def test_exception_availability_uses_canonical_keys_not_labels() -> None:
    key = "avg_loans"
    label = INDICATOR_REGISTRY[key].display_name
    exceptions = {
        "101": [{"indicator_key": label, "direction": "increase", "percentage": 10.0}]
    }

    assert key in get_available_exception_indicator_keys(list(INDICATOR_REGISTRY), exceptions, "101")


def test_exception_records_coexist_for_same_indicator_on_different_branches() -> None:
    key = "avg_loans"
    workspace = {
        "scenario_name": "سناریو",
        "primary_branch_code": "303",
        "period": "1404-04",
        "general_rules": [],
        "branch_exceptions": {
            "101": [{"indicator_key": key, "direction": "increase", "percentage": 10.0}],
            "202": [{"indicator_key": key, "direction": "decrease", "percentage": 5.0}],
        },
        "primary_branch_overrides": {},
    }
    from domain.multi_branch_contracts import ActorContext, ActorScope

    scenario = _build_scenario(workspace, 3, ActorContext("u", ActorScope.STAFF))

    assert [(item.branch_code, item.indicator_rules[0].indicator_key) for item in scenario.branch_exceptions] == [
        ("101", key),
        ("202", key),
    ]


def test_deleting_one_exception_pair_preserves_same_indicator_on_other_branch() -> None:
    key = "avg_loans"
    exceptions = {
        "101": [{"indicator_key": key, "direction": "increase", "percentage": 10.0}],
        "202": [{"indicator_key": key, "direction": "decrease", "percentage": 5.0}],
    }

    exceptions["101"].pop(0)
    if not exceptions["101"]:
        exceptions.pop("101")

    assert "101" not in exceptions
    assert exceptions["202"][0]["indicator_key"] == key
    assert key in _exception_indicator_options(exceptions, "101")
    assert key not in _exception_indicator_options(exceptions, "202")


def test_primary_percentage_rule_rows_retain_entered_percentage_and_calculated_values() -> None:
    row = pd.Series({"avg_deposits": 1000.0})
    rows = _primary_rule_rows(
        {"avg_deposits": {"input_mode": "percent", "input_value": 70.0, "resolved_raw_value": 1700.0}},
        row,
    )

    item = rows.iloc[0]
    assert item["method"] == "تغییر درصدی"
    assert item["entered"] == "۷۰٪ افزایش"
    assert item["baseline"] == "۱٬۰۰۰"
    assert item["change_amount"] == "۷۰۰"
    assert item["scenario_value"] == "۱٬۷۰۰"


def test_primary_percentage_input_accepts_persian_decimal_and_decrease_display() -> None:
    assert _parse_percentage_input("۱۲٫۵") == 12.5
    row = pd.Series({"avg_deposits": 1000.0})
    rows = _primary_rule_rows(
        {"avg_deposits": {"input_mode": "percent", "input_value": -12.5, "resolved_raw_value": 875.0}},
        row,
    )

    item = rows.iloc[0]
    assert item["entered"] == "۱۲٫۵٪ کاهش"
    assert item["change_amount"] == "−۱۲۵"
    assert item["scenario_value"] == "۸۷۵"


def test_review_rows_include_general_exception_and_primary_rule_families() -> None:
    key = next(iter(INDICATOR_REGISTRY))
    workspace = {
        "general_rules": [{"indicator_key": key, "direction": "increase", "percentage": 10.0}],
        "branch_exceptions": {"202": [{"indicator_key": key, "direction": "decrease", "percentage": 5.0}]},
        "primary_branch_overrides": {key: {"input_mode": "percent", "input_value": 70.0, "resolved_raw_value": 170.0}},
    }
    baseline = pd.Series({key: 100.0})

    assert "تمام شعب جامعه (کل شعب)" in _general_rule_review_rows(workspace).iloc[0]["دامنه اعمال"]
    assert "جایگزین قاعده عمومی" in _exception_rule_review_rows(workspace, {"202": "شعبه تست"}).iloc[0]["وضعیت تقدم"]
    assert _primary_rule_rows(workspace["primary_branch_overrides"], baseline).iloc[0]["entered"] == "۷۰٪ افزایش"


def test_review_card_builders_return_strings_for_all_rule_families() -> None:
    key = next(iter(INDICATOR_REGISTRY))
    general_rule = {"indicator_key": key, "direction": "increase", "percentage": 10.0}
    exception_rule = {"indicator_key": key, "direction": "decrease", "percentage": 5.0}
    primary_row = _primary_rule_rows(
        {key: {"input_mode": "percent", "input_value": 70.0, "resolved_raw_value": 170.0}},
        pd.Series({key: 100.0}),
    ).iloc[0].to_dict()

    assert isinstance(_render_review_rule_card(general_rule, 12), str)
    assert isinstance(_render_exception_card("202", exception_rule, {"202": "شعبه تست"}, {key}), str)
    assert isinstance(_render_primary_rule_card(primary_row), str)


def test_primary_review_cards_join_without_none_regression() -> None:
    keys = list(INDICATOR_REGISTRY)[:3]
    baseline = pd.Series({keys[0]: 100.0, keys[1]: 1000.0, keys[2]: 500.0})
    overrides = {
        keys[0]: {"input_mode": "percent", "input_value": 25.0, "resolved_raw_value": 125.0},
        keys[1]: {"input_mode": "absolute", "input_value": -50.0, "resolved_raw_value": 950.0},
        keys[2]: {"input_mode": "final", "input_value": 600.0, "resolved_raw_value": 600.0},
    }

    cards = [
        _render_primary_rule_card(row)
        for row in _primary_rule_rows(overrides, baseline).to_dict("records")
    ]
    body = "".join(cards)

    assert None not in cards
    assert body.count('multi-review-rule-card primary') == 3
    assert "ورودی کاربر" in body


def test_primary_review_card_handles_missing_optional_display_values() -> None:
    card = _render_primary_rule_card({
        "indicator": "شاخص تست",
        "method": None,
        "entered": None,
        "baseline": 0,
    })

    assert isinstance(card, str)
    assert "شاخص تست" in card
    assert "—" in card


def test_review_execution_remains_explicit_button() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "ui" / "multi_branch_page.py").read_text(encoding="utf-8")
    body = source.split("def _review", 1)[1].split("def _persistence_error", 1)[0]
    assert 'st.button("اجرای سناریو با مدل رسمی"' in body
    assert "MultiBranchRuleResolver.resolve" in body.split('if st.button("اجرای سناریو با مدل رسمی"', 1)[1]
