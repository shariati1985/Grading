"""Persian home for the three-mode sensitivity workspace."""

from __future__ import annotations

import html
import streamlit as st

from pathlib import Path

from domain.scenario_contracts import ScenarioType
from ui import initialize_session_state
from ui.components import render_empty_state
from ui.data_access import load_dashboard_data
from ui.sensitivity_labels import SCENARIO_TYPE_LABELS
from ui.sensitivity_components import render_scenario_cards
from ui.navigation import (
    HOME_VIEW,
    SAVED_SCENARIOS_VIEW,
    activate_requested_scenario,
    icon_svg,
    scenario_href,
)
from ui.formatters import persian_digits
from services.factory import create_local_scenario_service
from services.multi_branch_workspace_service import (
    SCENARIO_TYPE as MULTI_BRANCH_SCENARIO_TYPE,
    MultiBranchWorkspaceService,
    multi_branch_logical_key,
)
from services.scenario_workspace_service import PERSISTENCE_STATUS_LABELS, ScenarioWorkspaceService
from persistence.contracts import ScenarioPersistenceError
from ui.styles import apply_global_styles

st.set_page_config(
    page_title="پلتفرم تحلیل حساسیت درجه‌بندی شعب",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


ROOT = Path(__file__).resolve().parent


@st.cache_data(show_spinner="در حال بارگذاری اطلاعات مبنا...")
def _context():
    return load_dashboard_data(ROOT / "Data.xlsx", "1404-04")


@st.cache_resource
def _workspace_service() -> ScenarioWorkspaceService:
    return ScenarioWorkspaceService(create_local_scenario_service(ROOT))


@st.cache_resource
def _multi_branch_service() -> MultiBranchWorkspaceService:
    return MultiBranchWorkspaceService(create_local_scenario_service(ROOT))


def _open_saved(scenario_id: str, *, show_result: bool = False) -> None:
    data, _ = _context()
    record = next((item for item in _workspace_service().list_scenarios(limit=100) if item.scenario_id == scenario_id), None)
    mode = None if record is None else record.summary.get("scenario_type")
    if mode == MULTI_BRANCH_SCENARIO_TYPE:
        loaded = _multi_branch_service().load(
            scenario_id,
            branch_ids=data["branch_id"].astype(str).tolist(),
        )
        loaded.workspace["restore_warnings"] = list(loaded.warnings)
        loaded.workspace["show_persisted_result"] = bool(show_result and loaded.results)
        for key in list(st.session_state):
            if str(key).startswith("multi_"):
                st.session_state.pop(key, None)
        st.session_state["multi_branch_workspace"] = loaded.workspace
        st.session_state["sensitivity_draft"]["scenario_type"] = ScenarioType.MULTI_BRANCH
        st.switch_page("pages/2_Scenario_Builder.py")
    elif mode == ScenarioType.FOCUS_BRANCH_ONLY.value:
        loaded = _workspace_service().load_focus_scenario(
            scenario_id, baseline_data=data, periods=["1404-04"], restore_execution=show_result
        )
    else:
        loaded = _workspace_service().load_scenario(
            scenario_id, branch_ids=data["branch_id"].astype(str), periods=["1404-04"]
        )
        loaded.draft["persisted_result_summaries"] = list(loaded.results) if show_result else []
        loaded.draft["show_result"] = bool(show_result and loaded.results)
    st.session_state["sensitivity_draft"] = loaded.draft
    st.session_state["sensitivity_restore_warnings"] = list(loaded.warnings)
    st.switch_page("pages/2_Scenario_Builder.py")


def _new_version(scenario_id: str, *, mode: str | None = None) -> None:
    data, _ = _context()
    if mode == MULTI_BRANCH_SCENARIO_TYPE:
        created = _multi_branch_service().create_new_version(
            scenario_id,
            branch_ids=data["branch_id"].astype(str).tolist(),
        )
    else:
        created = _workspace_service().create_new_version(scenario_id)
    _open_saved(created.scenario_id)


def _group_saved_records(records) -> list[tuple[object, list[object]]]:
    grouped: dict[tuple[object, ...], list[object]] = {}
    order: list[tuple[object, ...]] = []
    for item in records:
        key = multi_branch_logical_key(item)
        group_key = key if key is not None else ("single", item.scenario_id)
        if group_key not in grouped:
            grouped[group_key] = []
            order.append(group_key)
        grouped[group_key].append(item)
    groups = []
    for key in order:
        items = grouped[key]
        latest = max(items, key=lambda record: (record.updated_at, record.created_at, record.scenario_id))
        groups.append((latest, items))
    return sorted(groups, key=lambda group: group[0].updated_at, reverse=True)


def _delete_record_group(items) -> None:
    for item in list(items):
        mode = item.summary.get("scenario_type")
        if mode == MULTI_BRANCH_SCENARIO_TYPE:
            _multi_branch_service().delete_scenario(item.scenario_id, item.row_version)
        else:
            _workspace_service().delete_scenario(item.scenario_id, item.row_version)


def current_home_view() -> str:
    return SAVED_SCENARIOS_VIEW if st.query_params.get("view") == SAVED_SCENARIOS_VIEW else HOME_VIEW


def home_markup(*, branch_count: int, saved_count: str) -> str:
    return (
        '<section class="home-page-header">'
        '<h1>سامانه تحلیل حساسیت و درجه‌بندی شعب</h1>'
        '<p>تحلیل سناریوهای مالی و عملیاتی شعب برای تصمیم‌گیری هوشمندانه و بهبود عملکرد</p>'
        '</section>'
        '<section class="home-decision-panel">'
        '<div class="decision-panel-pattern" aria-hidden="true"></div>'
        '<h2>تصمیم‌گیری هوشمند با تحلیل سناریو</h2>'
        '<p>با استفاده از سناریوهای متنوع، حساسیت متغیرهای کلیدی را بررسی کرده و بهترین مسیر را برای رشد و ارتقای عملکرد شعب انتخاب کنید.</p>'
        f'<a class="decision-panel-action" href="{html.escape(scenario_href(ScenarioType.FOCUS_BRANCH_ONLY))}" target="_self"><span aria-hidden="true">←</span> ایجاد سناریوی جدید</a>'
        '</section>'
        '<h2 class="home-section-title">انتخاب نوع سناریو</h2>'
    )


def overview_markup(*, branch_count: int, saved_count: str) -> str:
    document_icon = (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 3.5h8l3 3V20h-11z"/>'
        '<path d="M14.5 3.5v3h3"/><path d="M9 11h6"/><path d="M9 15h6"/></svg>'
    )
    clock_icon = (
        '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/>'
        '<path d="M12 7.5V12l3.25 2"/></svg>'
    )
    period = "1404-04".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    return (
        '<h2 class="home-section-title">نمای کلی مدیریتی</h2>'
        '<div class="home-overview-grid">'
        f'<article><span class="overview-icon">{icon_svg("bank")}</span><div class="overview-content"><b class="overview-value numeric-fa" dir="rtl">{persian_digits(f"{branch_count:,}")}</b><small class="overview-label">شعبه فعال در سامانه</small></div></article>'
        f'<article><span class="overview-icon">{document_icon}</span><div class="overview-content"><b class="overview-value numeric-fa" dir="rtl">{html.escape(persian_digits(saved_count))}</b><small class="overview-label">سناریوی ذخیره‌شده توسط کاربران</small></div></article>'
        f'<article><span class="overview-icon">{clock_icon}</span><div class="overview-content"><b class="overview-value numeric-fa" dir="rtl">{period}</b><small class="overview-label">دوره مبنای تحلیل</small></div></article>'
        '</div>'
    )


def render_home_page(data, saved_count: str) -> None:
    st.markdown(
        home_markup(
            branch_count=len(data),
            saved_count=saved_count,
        ),
        unsafe_allow_html=True,
    )
    render_scenario_cards()
    st.markdown(overview_markup(branch_count=len(data), saved_count=saved_count), unsafe_allow_html=True)


def render_saved_scenarios_view(data, records) -> None:
    st.markdown(
        '<section class="saved-view-header" id="saved-scenarios">'
        '<h1>سناریوهای ذخیره‌شده</h1>'
        f'<p>{len(records):,} سناریوی ذخیره‌شده در دسترس است.</p>'
        '</section>',
        unsafe_allow_html=True,
    )
    if not records:
        render_empty_state("هنوز سناریوی ذخیره‌شده‌ای وجود ندارد.")
        return
    try:
        branch_names = data.assign(branch_id=data["branch_id"].astype(str)).set_index("branch_id")["branch_name"].astype(str).to_dict()
    except (KeyError, ValueError):
        branch_names = {}
    for item, grouped_items in _group_saved_records(records):
        lineage = dict(item.summary.get("phase3b_lineage") or {})
        version = int(lineage.get("version_number") or 1)
        mode = item.summary.get("scenario_type")
        if mode == MULTI_BRANCH_SCENARIO_TYPE:
            mode_label = SCENARIO_TYPE_LABELS[ScenarioType.MULTI_BRANCH]
        else:
            try: mode_label = SCENARIO_TYPE_LABELS[ScenarioType(str(mode))]
            except ValueError: mode_label = "سناریوی قدیمی"
        branch_id = item.selected_branch_ids[0] if item.selected_branch_ids else None
        branch_label = branch_names.get(str(branch_id), str(branch_id)) if branch_id else "بدون شعبه منتخب"
        if mode == MULTI_BRANCH_SCENARIO_TYPE:
            definition = dict(item.summary.get("multi_branch_definition") or {})
            primary = definition.get("primary_branch_code") or branch_id
            branch_label = branch_names.get(str(primary), str(primary)) if primary else "بدون شعبه منتخب"
        with st.container(border=True):
            st.markdown(
                f'<div class="saved-scenario-card"><div><h3>{html.escape(item.scenario_name)}</h3>'
                f'<p>{html.escape(mode_label)} · {html.escape(branch_label)}</p></div>'
                f'<span>{html.escape(PERSISTENCE_STATUS_LABELS.get(item.status, "ذخیره‌شده"))}</span></div>',
                unsafe_allow_html=True,
            )
            metadata = st.columns(3)
            metadata[0].caption(f"نسخه {version}")
            metadata[1].caption(f"ایجاد: {item.created_at.astimezone().strftime('%Y-%m-%d %H:%M')}")
            metadata[2].caption(f"آخرین تغییر: {item.updated_at.astimezone().strftime('%Y-%m-%d %H:%M')}")
            actions = st.columns(4)
            if actions[0].button("بازکردن و ادامه", key=f"workspace_open_{item.scenario_id}", width="stretch"):
                try: _open_saved(item.scenario_id)
                except Exception: st.error("بازکردن سناریو انجام نشد. اطلاعات ذخیره‌شده را بازبینی کنید.")
            has_result = item.status == "executed" or bool(item.summary.get("has_saved_result"))
            if actions[1].button("مشاهده نتیجه", key=f"workspace_result_{item.scenario_id}", disabled=not has_result, width="stretch"):
                try: _open_saved(item.scenario_id, show_result=True)
                except Exception: st.error("بازیابی نتیجه سناریو انجام نشد. سناریو را باز کنید و دوباره اجرا کنید.")
            if not has_result:
                st.caption("این پیش‌نویس هنوز نتیجه رسمی ذخیره‌شده ندارد؛ آن را باز کنید و سناریو را اجرا کنید.")
            if actions[2].button("ایجاد نسخه جدید", key=f"workspace_version_{item.scenario_id}", width="stretch"):
                try: _new_version(item.scenario_id, mode=mode)
                except Exception: st.error("ایجاد نسخه جدید انجام نشد.")
            if actions[3].button("حذف سناریو", key=f"ask_delete_{item.scenario_id}", width="stretch"):
                st.session_state["confirm_scenario_delete"] = item.scenario_id
                st.rerun()
            if st.session_state.get("confirm_scenario_delete") == item.scenario_id:
                st.markdown("### حذف سناریو")
                st.warning(f"سناریوی «{item.scenario_name}» و تمام نسخه‌های آن حذف شود؟ این عملیات قابل بازگشت نیست.")
                confirm = st.columns(2)
                if confirm[0].button("انصراف", key=f"cancel_delete_{item.scenario_id}"):
                    st.session_state.pop("confirm_scenario_delete", None); st.rerun()
                if confirm[1].button("حذف قطعی", key=f"confirm_delete_{item.scenario_id}"):
                    try:
                        _delete_record_group(grouped_items)
                    except (ScenarioPersistenceError, ValueError, OSError): st.error("حذف سناریو انجام نشد.")
                    else:
                        st.session_state.pop("confirm_scenario_delete", None)
                        st.session_state.pop("multi_branch_workspace", None)
                        st.success("سناریو با موفقیت حذف شد.")
                        st.rerun()


def main() -> None:
    initialize_session_state()
    activate_requested_scenario()
    view = current_home_view()
    apply_global_styles(active_view=view)
    try:
        data, _ = _context()
    except (FileNotFoundError, ValueError, OSError):
        st.error("اطلاعات مبنا در دسترس نیست. لطفاً فایل داده را بررسی کنید.")
        return
    try:
        records = _workspace_service().list_scenarios(limit=100)
    except (ScenarioPersistenceError, ValueError, OSError):
        records = None
    if view == SAVED_SCENARIOS_VIEW:
        if records is None:
            st.error("فهرست سناریوهای ذخیره‌شده در دسترس نیست.")
            return
        render_saved_scenarios_view(data, records)
        return
    saved_count = "نامشخص" if records is None else f"{len(records):,}"
    render_home_page(data, saved_count)


if __name__ == "__main__":
    main()
