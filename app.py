"""Persian home for the three-mode sensitivity workspace."""

from __future__ import annotations

import streamlit as st

from pathlib import Path

from domain.scenario_contracts import ScenarioType
from ui import initialize_session_state
from ui.components import render_empty_state, render_page_header
from ui.data_access import load_dashboard_data
from ui.sensitivity_labels import MODE_COLORS, SCENARIO_DESCRIPTIONS, SCENARIO_TYPE_LABELS
from ui.sensitivity_state import SESSION_HISTORY_KEY, switch_scenario_mode
from services.factory import create_local_scenario_service
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


def _open_saved(scenario_id: str, *, show_result: bool = False) -> None:
    data, _ = _context()
    loaded = _workspace_service().load_scenario(
        scenario_id, branch_ids=data["branch_id"].astype(str), periods=["1404-04"]
    )
    loaded.draft["persisted_result_summaries"] = list(loaded.results) if show_result else []
    loaded.draft["show_result"] = bool(show_result and loaded.results)
    st.session_state["sensitivity_draft"] = loaded.draft
    st.session_state["sensitivity_restore_warnings"] = list(loaded.warnings)
    st.switch_page("pages/2_Scenario_Builder.py")


def _new_version(scenario_id: str) -> None:
    created = _workspace_service().create_new_version(scenario_id)
    _open_saved(created.scenario_id)


def _start(mode: ScenarioType) -> None:
    switch_scenario_mode(st.session_state, mode)
    st.switch_page("pages/2_Scenario_Builder.py")


def main() -> None:
    initialize_session_state()
    apply_global_styles()
    render_page_header(
        "سامانه تحلیل حساسیت مدل درجه‌بندی شعب",
        "تغییرات فرضی شاخص‌های شعب را اعمال کنید و اثر آن را بر امتیاز، رتبه و درجه مشاهده کنید.",
    )
    try:
        data, _ = _context()
    except (FileNotFoundError, ValueError, OSError):
        st.error("اطلاعات مبنا در دسترس نیست. لطفاً فایل داده را بررسی کنید.")
        return
    context = st.columns(2)
    context[0].metric("دوره مبنا", "1404-04")
    context[1].metric("تعداد شعب", f"{len(data):,}")
    st.markdown("### انتخاب نوع سناریو")
    icons = {ScenarioType.FOCUS_BRANCH_ONLY: "◈", ScenarioType.MULTI_BRANCH: "◆", ScenarioType.TARGET_RANK: "◎"}
    for column, mode in zip(st.columns(3), ScenarioType):
        with column:
            with st.container(border=True):
                st.markdown(f"<div class='mode-card {MODE_COLORS[mode]}'><span>{icons[mode]}</span><h3>{SCENARIO_TYPE_LABELS[mode]}</h3><p>{SCENARIO_DESCRIPTIONS[mode]}</p></div>", unsafe_allow_html=True)
                st.button("شروع", key=f"home_start_{mode.value}", type="primary", width="stretch", on_click=_start, args=(mode,))
    st.markdown("### سناریوهای این نشست")
    history = st.session_state[SESSION_HISTORY_KEY]
    if not history:
        render_empty_state("در این نشست هنوز سناریویی اجرا نشده است.")
    else:
        st.dataframe(history, width="stretch", hide_index=True)
    st.markdown("### سناریوهای ذخیره‌شده")
    try:
        records = _workspace_service().list_scenarios(limit=100)
    except (ScenarioPersistenceError, ValueError, OSError):
        st.error("فهرست سناریوهای ذخیره‌شده در دسترس نیست.")
        return
    if not records:
        render_empty_state("هنوز سناریوی ذخیره‌شده‌ای وجود ندارد.")
        return
    for item in records:
        lineage = dict(item.summary.get("phase3b_lineage") or {})
        version = int(lineage.get("version_number") or 1)
        mode = item.summary.get("scenario_type")
        try: mode_label = SCENARIO_TYPE_LABELS[ScenarioType(str(mode))]
        except ValueError: mode_label = "سناریوی قدیمی"
        with st.expander(f"{item.scenario_name} — نسخه {version} — {PERSISTENCE_STATUS_LABELS.get(item.status, 'ذخیره‌شده')}"):
            st.caption(f"نوع: {mode_label} | شعبه محوری: {item.selected_branch_ids[0] if item.selected_branch_ids else '—'} | دوره: {item.baseline_period} | آخرین تغییر: {item.updated_at.astimezone().strftime('%Y-%m-%d %H:%M')}")
            actions = st.columns(3)
            actions[0].button("بازکردن", key=f"workspace_open_{item.scenario_id}", on_click=_open_saved, args=(item.scenario_id,), width="stretch")
            actions[1].button("ایجاد نسخه جدید", key=f"workspace_version_{item.scenario_id}", on_click=_new_version, args=(item.scenario_id,), width="stretch")
            actions[2].button("مشاهده نتیجه", key=f"workspace_result_{item.scenario_id}", disabled=item.status != "executed", on_click=_open_saved, args=(item.scenario_id,), kwargs={"show_result": True}, width="stretch")


if __name__ == "__main__":
    main()
