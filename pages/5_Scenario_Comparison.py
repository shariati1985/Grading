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
from ui import initialize_session_state
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
VISIBILITY_LABELS: Final[dict[str, str]] = {"private": "شخصی", "shared": "مشترک"}


@st.cache_resource
def get_scenario_service(project_root: Path) -> ScenarioManagementService:
    return create_local_scenario_service(project_root)


def _open_in_builder(
    service: ScenarioManagementService, scenario: ScenarioRecord
) -> None:
    record, changes, _, edit_modes = service.load_scenario_editor(
        scenario.scenario_id
    )
    st.session_state.update(
        {
            "scenario_name": record.scenario_name,
            "selected_regions": [],
            "selected_branches": list(record.selected_branch_ids),
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
            "_selected_region_input": "همه مناطق",
            "_selected_branches_input": list(record.selected_branch_ids),
            "_scenario_visibility": record.visibility,
            "editor_version": st.session_state.get("editor_version", 0) + 1,
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
                "سطح دسترسی": VISIBILITY_LABELS[item.visibility],
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
        "مدیریت سناریوهای شخصی و سناریوهای مشترک قابل مشاهده",
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
            owner = item.owner_user_id == service.current_user.user_id
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
                        disabled=not owner or item.status == "archived",
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
                        disabled=not owner,
                        width="stretch",
                    ):
                        try:
                            service.delete_scenario(item.scenario_id, item.row_version)
                        except Exception as exc:
                            _show_error(exc)
                        else:
                            st.rerun()
                if not owner:
                    st.caption("سناریوی مشترک متعلق به کاربر دیگر فقط قابل بازکردن و کپی است.")
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
