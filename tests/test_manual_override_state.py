"""Independent UUID-backed manual override row state tests."""

from __future__ import annotations

from engine.indicator_registry import INDICATOR_REGISTRY
from engine.scenario_rule_engine import RuleOperation, ScenarioRuleEngine
from ui.manual_override_state import (
    NO_CHANGE_LABEL,
    delete_override_row,
    delete_override_group,
    domain_rule_to_ui,
    duplicate_override_keys,
    new_override_row,
    normalize_rule_widget_state,
    restore_override_rows,
    replace_override_group,
    serialize_override_rows,
    to_domain_overrides,
    update_override_row,
    ui_rule_to_domain,
)


def make_row(row_id: str, branch: str, indicator: str):
    return new_override_row(
        row_id_factory=lambda: row_id,
        branch_id=branch,
        indicator_key=indicator,
        operation=RuleOperation.SET_VALUE,
        input_value=10,
    )


def test_two_rows_retain_different_branch_ids() -> None:
    rows = [make_row("a", "101", "deposit_count"), make_row("b", "202", "loan_count")]
    assert [item.branch_id for item in to_domain_overrides(rows)] == ["101", "202"]


def test_three_rows_do_not_reuse_first_branch() -> None:
    rows = [
        make_row("a", "101", "deposit_count"),
        make_row("b", "202", "loan_count"),
        make_row("c", "303", "profit_loss"),
    ]
    assert [row["branch_id"] for row in rows] == ["101", "202", "303"]


def test_same_branch_with_two_or_all_eight_indicators_is_valid() -> None:
    two = [make_row("a", "101", "deposit_count"), make_row("b", "101", "loan_count")]
    assert duplicate_override_keys(two) == set()
    all_eight = [
        make_row(str(index), "101", indicator)
        for index, indicator in enumerate(INDICATOR_REGISTRY)
    ]
    assert duplicate_override_keys(all_eight) == set()
    assert len(to_domain_overrides(all_eight)) == 8


def test_only_same_branch_and_indicator_is_duplicate() -> None:
    duplicate = [make_row("a", "101", "loan_count"), make_row("b", "101", "loan_count")]
    assert duplicate_override_keys(duplicate) == {("101", "loan_count")}
    different_branches = [make_row("a", "101", "loan_count"), make_row("b", "202", "loan_count")]
    assert duplicate_override_keys(different_branches) == set()


def test_deleting_one_row_preserves_remaining_rows_and_order() -> None:
    rows = [
        make_row("a", "101", "deposit_count"),
        make_row("b", "202", "loan_count"),
        make_row("c", "303", "profit_loss"),
    ]
    remaining = delete_override_row(rows, "b")
    assert [(row["row_id"], row["branch_id"]) for row in remaining] == [
        ("a", "101"),
        ("c", "303"),
    ]
    assert len(rows) == 3


def test_editing_one_row_does_not_mutate_another_or_input_list() -> None:
    rows = [make_row("a", "101", "deposit_count"), make_row("b", "202", "loan_count")]
    updated = update_override_row(rows, "b", branch_id="303", input_value=99.0)
    assert updated[0] == rows[0]
    assert updated[1]["branch_id"] == "303"
    assert updated[1]["input_value"] == 99
    assert rows[1]["branch_id"] == "202"


def test_preview_includes_every_independent_override(scenario_rule_baseline) -> None:
    rows = [make_row("a", "101", "deposit_count"), make_row("b", "202", "loan_count")]
    preview = ScenarioRuleEngine.preview(
        ["101", "202"], scenario_rule_baseline, [], to_domain_overrides(rows)
    )
    assert preview.manual_override_count == 2
    overridden = [row for row in preview.rows if row.change_source == "manual_override"]
    assert [(row.branch_id, row.indicator_key) for row in overridden] == [
        ("101", "deposit_count"),
        ("202", "loan_count"),
    ]


def test_persisted_rows_restore_all_fields_and_stable_ids() -> None:
    rows = [make_row("uuid-a", "101", "deposit_count"), make_row("uuid-b", "202", "profit_loss")]
    restored = restore_override_rows(serialize_override_rows(rows))
    assert restored == rows


def test_legacy_rows_without_ids_restore_deterministically() -> None:
    legacy = [
        {"branch_id": "101", "indicator_key": "avg_loans", "operation": "SET_VALUE", "value": 42.0},
        {"branch_id": "202", "indicator_key": "profit_loss", "operation": "ABSOLUTE_CHANGE", "value": -5.0},
    ]
    first = restore_override_rows(legacy)
    second = restore_override_rows(legacy)
    assert first == second
    assert [row["branch_id"] for row in first] == ["101", "202"]


def test_focus_and_exception_sources_survive_serialization_and_rerun() -> None:
    focus = new_override_row(
        row_id_factory=lambda: "focus-row", group_id="focus-group", branch_id="101",
        indicator_key="deposit_count", operation=RuleOperation.PERCENT_CHANGE,
        input_value=-12.5, source="focus_branch_override",
    )
    exception = new_override_row(
        row_id_factory=lambda: "exception-row", group_id="exception-group", branch_id="202",
        indicator_key="loan_count", operation=RuleOperation.ABSOLUTE_CHANGE,
        input_value=9, source="branch_exception",
    )
    restored_focus = restore_override_rows(
        serialize_override_rows([focus]), default_source="focus_branch_override"
    )
    restored_exception = restore_override_rows(serialize_override_rows([exception]))
    assert restored_focus == [focus]
    assert restored_exception == [exception]
    assert to_domain_overrides(restored_focus)[0].source == "focus_branch_override"
    assert to_domain_overrides(restored_exception)[0].source == "branch_exception"


def test_returning_one_indicator_to_no_change_removes_only_that_override() -> None:
    rows = [
        new_override_row(row_id_factory=lambda: "a", group_id="g", branch_id="101", indicator_key="deposit_count"),
        new_override_row(row_id_factory=lambda: "b", group_id="g", branch_id="101", indicator_key="loan_count"),
    ]
    replacement = [dict(rows[1])]
    assert replace_override_group(rows, "g", replacement) == replacement


def test_group_edit_and_delete_are_isolated() -> None:
    group_a = [
        new_override_row(
            row_id_factory=lambda: "a1", group_id="group-a", branch_id="101",
            indicator_key="deposit_count", input_value=1,
        ),
        new_override_row(
            row_id_factory=lambda: "a2", group_id="group-a", branch_id="101",
            indicator_key="loan_count", input_value=2,
        ),
    ]
    group_b = [
        new_override_row(
            row_id_factory=lambda: "b1", group_id="group-b", branch_id="202",
            indicator_key="profit_loss", input_value=-5,
        )
    ]
    replacement = [
        new_override_row(
            row_id_factory=lambda: "a1", group_id="group-a", branch_id="101",
            indicator_key="deposit_count", input_value=99,
        )
    ]
    edited = replace_override_group([*group_a, *group_b], "group-a", replacement)
    assert edited[-1] == group_b[0]
    assert edited[0]["input_value"] == 99
    assert delete_override_group(edited, "group-a") == group_b


def test_no_change_disables_value_and_discards_stale_numeric_value() -> None:
    state = {"operation": NO_CHANGE_LABEL, "value": 123.0}
    assert normalize_rule_widget_state(
        state, operation_key="operation", value_key="value"
    ) is True
    assert state["value"] == 0.0
    assert ui_rule_to_domain(state["operation"], state["value"]) is None


def test_active_operation_keeps_value_enabled() -> None:
    state = {"operation": "افزایش درصدی"}
    assert normalize_rule_widget_state(
        state, operation_key="operation", value_key="value", default_value=7.5
    ) is False
    assert state["value"] == 7.5


def test_ui_operations_convert_to_signed_domain_values() -> None:
    assert ui_rule_to_domain("افزایش درصدی", 10) == (
        RuleOperation.PERCENT_CHANGE,
        10,
    )
    assert ui_rule_to_domain("کاهش درصدی", 10) == (
        RuleOperation.PERCENT_CHANGE,
        -10,
    )
    assert ui_rule_to_domain("افزایش عددی", 20) == (
        RuleOperation.ABSOLUTE_CHANGE,
        20,
    )
    assert ui_rule_to_domain("کاهش عددی", 20) == (
        RuleOperation.ABSOLUTE_CHANGE,
        -20,
    )
    assert ui_rule_to_domain("تعیین مقدار جدید", -5) == (
        RuleOperation.SET_VALUE,
        -5,
    )


def test_signed_domain_values_round_trip_to_ui_labels() -> None:
    assert domain_rule_to_ui(RuleOperation.PERCENT_CHANGE, -12.5) == (
        "کاهش درصدی",
        12.5,
    )
    assert domain_rule_to_ui(RuleOperation.ABSOLUTE_CHANGE, 9) == (
        "افزایش عددی",
        9,
    )
    assert domain_rule_to_ui(RuleOperation.SET_VALUE, -3) == (
        "تعیین مقدار جدید",
        -3,
    )


def test_no_change_rows_are_not_converted_to_preview_overrides(
    scenario_rule_baseline,
) -> None:
    converted = ui_rule_to_domain(NO_CHANGE_LABEL, 99)
    rows = []
    if converted is not None:
        rows.append(
            new_override_row(
                branch_id="101",
                indicator_key="deposit_count",
                operation=converted[0],
                input_value=converted[1],
            )
        )
    preview = ScenarioRuleEngine.preview(
        ["101"], scenario_rule_baseline, [], to_domain_overrides(rows)
    )
    assert preview.manual_override_count == 0
    assert {row.change_source for row in preview.rows} == {"baseline"}
