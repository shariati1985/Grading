"""Saved scenario workspace with ownership-aware actions."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd
import streamlit as st

from persistence.contracts import AuthorizationError, ConcurrencyError, ScenarioPersistenceError
from persistence.models import ScenarioRecord
from services.factory import create_local_scenario_service
from services.scenario_management_service import ScenarioManagementService
from services.selection_scope import SelectionScope
from engine.scenario_rule_engine import RuleOperation
from ui import initialize_session_state
from ui.manual_override_state import restore_override_rows
from ui.components import render_empty_state, render_page_header
from ui.styles import apply_global_styles
from ui.tables import render_table

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PAGE_SIZE: Final[int] = 25
STATUS_LABELS: Final[dict[str, str]] = {
    "draft": "پیش‌نویس",
    "executed": "اجراشده",
    "archived": "بایگانی‌شده",
}


@st.cache_resource
def get_scenario_service(project_root: Path) -> ScenarioManagementService:
    return create_local_scenario_service(project_root)


def _open_in_builder(
    service: ScenarioManagementService, scenario: ScenarioRecord
) -> None:
    record, changes, _, edit_modes = service.load_scenario_editor(
        scenario.scenario_id
    )
    definition = dict(record.summary.get("scenario_definition", {}))
    if not definition:
        definition = {
            "schema_version": 0,
            "selection_scope": "SELECTED_BRANCHES",
            "selection_inputs": {"selected_branch_ids": list(record.selected_branch_ids)},
            "bulk_rules": [],
            "manual_overrides": [
                {
                    "branch_id": item.branch_id,
                    "indicator_key": item.indicator_key,
                    "operation": RuleOperation.SET_VALUE.value,
                    "value": item.scenario_value,
                }
                for item in changes
            ],
            "validation_status": "legacy",
        }

    widget_state: dict[str, object] = {}
    for item in definition.get(
        "network_bulk_rules", definition.get("bulk_rules", [])
    ):
        operation = RuleOperation(str(item["operation"]))
        value = float(item["value"])
        if operation is RuleOperation.PERCENT_CHANGE:
            label = "افزایش درصدی" if value >= 0 else "کاهش درصدی"
            widget_value = abs(value)
        elif operation is RuleOperation.ABSOLUTE_CHANGE:
            label = "افزایش عددی" if value >= 0 else "کاهش عددی"
            widget_value = abs(value)
        else:
            label, widget_value = "تعیین مقدار جدید", value
        widget_state[f"network_{item['indicator_key']}_operation"] = label
        widget_state[f"network_{item['indicator_key']}_value"] = widget_value
        widget_state[f"_bulk_operation_{item['indicator_key']}"] = label
        widget_state[f"_bulk_value_{item['indicator_key']}"] = widget_value
    saved_focus_id = str(
        definition.get("focus_branch_id")
        or (
            service.current_user.branch_id
            if service.current_user.branch_id in record.selected_branch_ids
            else record.selected_branch_ids[0] if record.selected_branch_ids else ""
        )
    )
    saved_focus_source = str(
        definition.get("focus_branch_source")
        or (
            "ASSIGNED_USER_BRANCH"
            if saved_focus_id == service.current_user.branch_id
            else "USER_SELECTED_BRANCH"
        )
    )
    manual_items = list(definition.get("manual_overrides", []))
    if not manual_items:
        for branch_id, indicators in dict(
            definition.get("branch_exception_groups", {})
        ).items():
            for indicator_key, item in dict(indicators).items():
                manual_items.append(
                    {
                        "branch_id": str(branch_id),
                        "indicator_key": str(indicator_key),
                        "operation": item["operation"],
                        "input_value": item.get("input_value", item.get("value", 0.0)),
                        "source": "branch_exception",
                    }
                )
    user_items = list(
        definition.get(
            "focus_branch_overrides", definition.get("user_branch_overrides", [])
        )
    )
    if not user_items and saved_focus_id:
        user_items = [
            item for item in manual_items
            if str(item.get("branch_id")) == saved_focus_id
        ]
        manual_items = [
            item for item in manual_items
            if str(item.get("branch_id")) != saved_focus_id
        ]
    focus_branch_override_rows = restore_override_rows(
        user_items, default_source="focus_branch_override"
    )
    manual_override_rows = restore_override_rows(manual_items)
    manual_override_groups: list[dict[str, str]] = []
    seen_groups: set[str] = set()
    for item in manual_override_rows:
        if item["group_id"] not in seen_groups:
            manual_override_groups.append(
                {"group_id": item["group_id"], "branch_id": item["branch_id"]}
            )
            seen_groups.add(item["group_id"])

    try:
        saved_scope = SelectionScope(str(definition.get("selection_scope")))
    except ValueError:
        saved_scope = SelectionScope.SELECTED_BRANCHES
    selection_inputs = dict(definition.get("selection_inputs", {}))
    saved_regions = list(selection_inputs.get("selected_regions", []))

    for key in list(st.session_state):
        if str(key).startswith(
            (
                "override_branch_",
                "override_indicator_",
                "override_operation_",
                "override_value_",
                "override_delete_",
                "user_override_operation_",
                "user_override_value_",
                "focus_",
                "exception_",
                "network_",
            )
        ):
            st.session_state.pop(key, None)

    st.session_state.update(
        {
            "scenario_name": record.scenario_name,
            "selection_scope": saved_scope.value,
            "selected_regions": saved_regions,
            "selected_branch_ids": list(record.selected_branch_ids),
            "scenario_definition": definition,
            "focus_branch_id": saved_focus_id or None,
            "focus_branch_source": saved_focus_source if saved_focus_id else None,
            "manual_override_rows": manual_override_rows,
            "manual_override_groups": manual_override_groups,
            "focus_branch_override_rows": focus_branch_override_rows,
            "focus_branch_overrides": focus_branch_override_rows,
            "branch_exception_groups": {
                group["branch_id"]: {
                    row["indicator_key"]: {
                        "operation": row["operation"],
                        "input_value": row["input_value"],
                    }
                    for row in manual_override_rows
                    if row["group_id"] == group["group_id"]
                }
                for group in manual_override_groups
            },
            "scenario_mode": str(
                definition.get(
                    "scenario_mode",
                    "ONLY_USER_BRANCH"
                    if record.selected_branch_ids == [service.current_user.branch_id]
                    else "USER_AND_OTHERS",
                )
            ),
            "scenario_changes": changes,
            "scenario_dataframe": None,
            "scenario_results": None,
            "scenario_outputs": None,
            "comparison_results": None,
            "scenario_executed": False,
            "current_scenario_id": record.scenario_id,
            "current_scenario_row_version": record.row_version,
            "current_scenario_dirty": False,
            "current_scenario_record": record,
            "loaded_scenario_changes": changes,
            "loaded_scenario_edit_modes": edit_modes,
            "indicator_editor_state": {},
            "_editor_branches": None,
            "_scenario_name_input": record.scenario_name,
            "_focus_branch_input": saved_focus_id or None,
            "_selection_scope_input": saved_scope,
            "_scenario_mode_input": str(
                definition.get(
                    "scenario_mode",
                    "ONLY_USER_BRANCH"
                    if record.selected_branch_ids == [service.current_user.branch_id]
                    else "USER_AND_OTHERS",
                )
            ),
            "_other_selection_scope_input": (
                saved_scope
                if saved_scope in {
                    SelectionScope.SELECTED_BRANCHES,
                    SelectionScope.SELECTED_REGIONS,
                    SelectionScope.ALL_BRANCHES,
                }
                else SelectionScope.SELECTED_BRANCHES
            ),
            "_selected_regions_input": saved_regions,
            "_selected_branch_ids_input": list(record.selected_branch_ids),
            "editor_version": st.session_state.get("editor_version", 0) + 1,
            **widget_state,
        }
    )
    st.switch_page("pages/2_Scenario_Builder.py")


def _headers_table(records: list[ScenarioRecord]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "نام سناریو": item.scenario_name,
                "مالک": item.owner_display_name,
                "دوره": item.baseline_period,
                "وضعیت": STATUS_LABELS[item.status],
                "تعداد شعب تغییریافته": int(
                    item.summary.get("changed_branch_count", len(item.selected_branch_ids))
                ),
                "تاریخ ایجاد": item.created_at.astimezone().strftime("%Y-%m-%d %H:%M"),
                "آخرین ویرایش": item.updated_at.astimezone().strftime("%Y-%m-%d %H:%M"),
            }
            for item in records
        ]
    )


def _show_error(exc: Exception) -> None:
    if isinstance(exc, ConcurrencyError):
        st.error("سناریو در نشست دیگری تغییر کرده است. فهرست را بازخوانی کنید.")
    elif isinstance(exc, AuthorizationError):
        st.error("شما مجوز انجام این عملیات روی سناریو را ندارید.")
    elif isinstance(exc, (ScenarioPersistenceError, ValueError)):
        st.error(str(exc))
    else:
        st.error("عملیات سناریو انجام نشد. لطفاً دوباره تلاش کنید.")


def main() -> None:
    initialize_session_state()
    apply_global_styles()
    render_page_header(
        "سناریوهای ذخیره‌شده",
        "مدیریت سناریوهای شخصی ذخیره‌شده",
    )
    try:
        service = get_scenario_service(ROOT)
    except (FileNotFoundError, ValueError, OSError):
        st.error("سرویس ذخیره‌سازی سناریو در دسترس نیست.")
        st.stop()

    filters = st.columns([2, 1])
    with filters[0]:
        search = st.text_input("جست‌وجو بر اساس نام سناریو", key="_saved_search")
    with filters[1]:
        status_filter = st.selectbox(
            "وضعیت",
            options=[None, "draft", "executed", "archived"],
            format_func=lambda value: "همه وضعیت‌ها" if value is None else STATUS_LABELS[value],
            key="_saved_status",
        )
    filter_signature = (search, status_filter)
    if st.session_state.get("_saved_filter_signature") != filter_signature:
        st.session_state["_saved_filter_signature"] = filter_signature
        st.session_state["_saved_offset"] = 0
    offset = int(st.session_state.get("_saved_offset", 0))

    try:
        records = service.list_visible(
            status=status_filter,
            search=search,
            limit=PAGE_SIZE,
            offset=offset,
        )
    except Exception as exc:
        _show_error(exc)
        return
    if not records:
        render_empty_state("سناریویی مطابق فیلترهای انتخاب‌شده یافت نشد.")
    else:
        render_table(_headers_table(records), height=470)

        st.subheader("عملیات سناریو")
        for item in records:
            with st.expander(
                f"{item.scenario_name} — {item.owner_display_name} — {STATUS_LABELS[item.status]}"
            ):
                action_columns = st.columns(4)
                with action_columns[0]:
                    if st.button("بازکردن", key=f"open_{item.scenario_id}", width="stretch"):
                        try:
                            _open_in_builder(service, item)
                        except Exception as exc:
                            _show_error(exc)
                with action_columns[1]:
                    if st.button("کپی", key=f"copy_{item.scenario_id}", width="stretch"):
                        try:
                            copied = service.copy_scenario(
                                item.scenario_id, f"کپی - {item.scenario_name}"
                            )
                        except Exception as exc:
                            _show_error(exc)
                        else:
                            st.success(f"نسخه شخصی «{copied.scenario_name}» ایجاد شد.")
                with action_columns[2]:
                    if st.button(
                        "بایگانی",
                        key=f"archive_{item.scenario_id}",
                        disabled=item.status == "archived",
                        width="stretch",
                    ):
                        try:
                            service.archive_scenario(item.scenario_id, item.row_version)
                        except Exception as exc:
                            _show_error(exc)
                        else:
                            st.rerun()
                with action_columns[3]:
                    if st.button(
                        "حذف",
                        key=f"delete_{item.scenario_id}",
                        width="stretch",
                    ):
                        try:
                            service.delete_scenario(item.scenario_id, item.row_version)
                        except Exception as exc:
                            _show_error(exc)
                        else:
                            st.rerun()
                with st.expander("اطلاعات فنی"):
                    st.code(
                        f"scenario_id: {item.scenario_id}\nrow_version: {item.row_version}",
                        language=None,
                    )

    pagination = st.columns([1, 1, 4])
    with pagination[0]:
        if st.button("صفحه قبل", disabled=offset == 0, key="_saved_previous"):
            st.session_state["_saved_offset"] = max(0, offset - PAGE_SIZE)
            st.rerun()
    with pagination[1]:
        if st.button("صفحه بعد", disabled=len(records) < PAGE_SIZE, key="_saved_next"):
            st.session_state["_saved_offset"] = offset + PAGE_SIZE
            st.rerun()
    st.caption(f"نمایش رکوردهای {offset + 1} تا {offset + len(records)}")


main()
