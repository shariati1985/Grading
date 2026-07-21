"""Stable, independently editable view state for manual override rows."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, TypedDict
from uuid import NAMESPACE_URL, uuid4, uuid5

from engine.scenario_rule_engine import ManualOverride, RuleOperation

NO_CHANGE_LABEL = "بدون تغییر"
RULE_UI_OPTIONS = (
    NO_CHANGE_LABEL,
    "افزایش درصدی",
    "کاهش درصدی",
    "افزایش عددی",
    "کاهش عددی",
    "تعیین مقدار جدید",
)


class ManualOverrideRow(TypedDict):
    row_id: str
    group_id: str
    branch_id: str
    indicator_key: str
    operation: str
    input_value: float
    source: str


def ui_rule_to_domain(label: str, value: float) -> tuple[RuleOperation, float] | None:
    if label == NO_CHANGE_LABEL:
        return None
    operation = {
        "افزایش درصدی": RuleOperation.PERCENT_CHANGE,
        "کاهش درصدی": RuleOperation.PERCENT_CHANGE,
        "افزایش عددی": RuleOperation.ABSOLUTE_CHANGE,
        "کاهش عددی": RuleOperation.ABSOLUTE_CHANGE,
        "تعیین مقدار جدید": RuleOperation.SET_VALUE,
    }[label]
    signed = (
        value
        if operation is RuleOperation.SET_VALUE
        else -abs(value) if label in {"کاهش درصدی", "کاهش عددی"} else abs(value)
    )
    return operation, signed


def domain_rule_to_ui(operation: RuleOperation, value: float) -> tuple[str, float]:
    if operation is RuleOperation.PERCENT_CHANGE:
        return ("افزایش درصدی" if value >= 0 else "کاهش درصدی", abs(value))
    if operation is RuleOperation.ABSOLUTE_CHANGE:
        return ("افزایش عددی" if value >= 0 else "کاهش عددی", abs(value))
    return "تعیین مقدار جدید", value


def normalize_rule_widget_state(
    state: dict[str, Any],
    *,
    operation_key: str,
    value_key: str,
    default_label: str = NO_CHANGE_LABEL,
    default_value: float = 0.0,
) -> bool:
    """Return True when the numeric widget should be disabled."""
    state.setdefault(operation_key, default_label)
    option = str(state[operation_key])
    if option == NO_CHANGE_LABEL:
        state[value_key] = 0.0
        return True
    state.setdefault(value_key, default_value)
    return False


def new_override_row(
    *,
    branch_id: str,
    indicator_key: str,
    operation: RuleOperation = RuleOperation.SET_VALUE,
    input_value: float = 0.0,
    row_id_factory: Callable[[], str] = lambda: str(uuid4()),
    group_id: str | None = None,
    source: str = "manual_override",
) -> ManualOverrideRow:
    return {
        "row_id": row_id_factory(),
        "group_id": group_id or str(uuid4()),
        "branch_id": str(branch_id),
        "indicator_key": indicator_key,
        "operation": operation.value,
        "input_value": float(input_value),
        "source": source,
    }


def update_override_row(
    rows: list[ManualOverrideRow], row_id: str, **changes: Any
) -> list[ManualOverrideRow]:
    """Return a copied list with exactly one row updated in place."""
    updated = [dict(row) for row in rows]
    matches = [index for index, row in enumerate(updated) if row["row_id"] == row_id]
    if len(matches) != 1:
        raise ValueError("Manual override row_id must identify exactly one row")
    updated[matches[0]].update(changes)
    return updated  # type: ignore[return-value]


def delete_override_row(
    rows: list[ManualOverrideRow], row_id: str
) -> list[ManualOverrideRow]:
    """Return rows in original order with only the identified row removed."""
    remaining = [dict(row) for row in rows if row["row_id"] != row_id]
    if len(remaining) != len(rows) - 1:
        raise ValueError("Manual override row_id must identify exactly one row")
    return remaining  # type: ignore[return-value]


def delete_override_group(
    rows: list[ManualOverrideRow], group_id: str
) -> list[ManualOverrideRow]:
    return [dict(row) for row in rows if row["group_id"] != group_id]  # type: ignore[return-value]


def replace_override_group(
    rows: list[ManualOverrideRow],
    group_id: str,
    replacement: list[ManualOverrideRow],
) -> list[ManualOverrideRow]:
    """Replace one group without changing the relative state of other groups."""
    first = next(
        (index for index, row in enumerate(rows) if row["group_id"] == group_id),
        len(rows),
    )
    remaining = [dict(row) for row in rows if row["group_id"] != group_id]
    insertion = min(first, len(remaining))
    return [*remaining[:insertion], *[dict(row) for row in replacement], *remaining[insertion:]]  # type: ignore[return-value]


def duplicate_override_keys(
    rows: Iterable[ManualOverrideRow],
) -> set[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    duplicates: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row["branch_id"]), str(row["indicator_key"]))
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return duplicates


def to_domain_overrides(
    rows: Iterable[ManualOverrideRow], *, default_source: str = "branch_exception"
) -> list[ManualOverride]:
    return [
        ManualOverride(
            str(row["branch_id"]),
            str(row["indicator_key"]),
            RuleOperation(str(row["operation"])),
            float(row["input_value"]),
            str(row.get("source", default_source)),
        )
        for row in rows
    ]


def serialize_override_rows(rows: Iterable[ManualOverrideRow]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def restore_override_rows(
    items: Iterable[dict[str, Any]], *, default_source: str = "branch_exception"
) -> list[ManualOverrideRow]:
    """Restore new rows and deterministically identify legacy rows without IDs."""
    restored: list[ManualOverrideRow] = []
    for index, item in enumerate(items):
        branch_id = str(item["branch_id"])
        indicator_key = str(item["indicator_key"])
        operation = RuleOperation(str(item["operation"]))
        input_value = float(item.get("input_value", item.get("value", 0.0)))
        source = str(item.get("source", default_source))
        row_id = str(item.get("row_id") or uuid5(
            NAMESPACE_URL,
            f"legacy-override:{index}:{branch_id}:{indicator_key}:{operation.value}",
        ))
        group_id = str(item.get("group_id") or uuid5(
            NAMESPACE_URL, f"legacy-override-group:{branch_id}"
        ))
        restored.append(
            new_override_row(
                branch_id=branch_id,
                indicator_key=indicator_key,
                operation=operation,
                input_value=input_value,
                group_id=group_id,
                row_id_factory=lambda value=row_id: value,
                source=source,
            )
        )
    return restored
