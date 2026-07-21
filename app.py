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
from ui.sensitivity_state import SESSION_HISTORY_KEY
from ui.sensitivity_components import render_scenario_cards
from ui.navigation import activate_requested_scenario
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
    record = next((item for item in _workspace_service().list_scenarios(limit=100) if item.scenario_id == scenario_id), None)
    mode = None if record is None else record.summary.get("scenario_type")
    if mode == ScenarioType.FOCUS_BRANCH_ONLY.value:
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


def _new_version(scenario_id: str) -> None:
    created = _workspace_service().create_new_version(scenario_id)
    _open_saved(created.scenario_id)


def main() -> None:
    initialize_session_state()
    activate_requested_scenario()
    apply_global_styles()
    st.markdown(
        '<header class="bank-hero"><div class="bank-logo-slot" aria-label="بانک اقتصاد نوین"></div>'
        '<div><h1>سامانه تحلیل حساسیت درجه‌بندی شعب</h1>'
        '<p>ارزیابی اثر تغییر شاخص‌ها بر رتبه، امتیاز و درجه شعبه</p></div></header>',
        unsafe_allow_html=True,
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
    render_scenario_cards()
    st.markdown("### سناریوهای این نشست")
    history = st.session_state[SESSION_HISTORY_KEY]
    if not history:
        render_empty_state("در این نشست هنوز سناریویی اجرا نشده است.")
    else:
        st.dataframe(history, width="stretch", hide_index=True)
    st.markdown("### سناریوهای ذخیره‌شده")
    st.markdown('<div id="saved-scenarios"></div>', unsafe_allow_html=True)
    try:
        records = _workspace_service().list_scenarios(limit=100)
    except (ScenarioPersistenceError, ValueError, OSError):
        st.error("فهرست سناریوهای ذخیره‌شده در دسترس نیست.")
        return
    if not records:
        render_empty_state("هنوز سناریوی ذخیره‌شده‌ای وجود ندارد.")
        return
    branch_names = data.assign(branch_id=data["branch_id"].astype(str)).set_index("branch_id")["branch_name"].astype(str).to_dict()
    for item in records:
        lineage = dict(item.summary.get("phase3b_lineage") or {})
        version = int(lineage.get("version_number") or 1)
        mode = item.summary.get("scenario_type")
        try: mode_label = SCENARIO_TYPE_LABELS[ScenarioType(str(mode))]
        except ValueError: mode_label = "سناریوی قدیمی"
        branch_id = item.selected_branch_ids[0] if item.selected_branch_ids else None
        branch_label = branch_names.get(str(branch_id), str(branch_id)) if branch_id else "بدون شعبه منتخب"
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
            if actions[1].button("مشاهده نتیجه", key=f"workspace_result_{item.scenario_id}", disabled=item.status != "executed", width="stretch"):
                try: _open_saved(item.scenario_id, show_result=True)
                except Exception: st.error("بازیابی نتیجه سناریو انجام نشد. سناریو را باز کنید و دوباره اجرا کنید.")
            if item.status != "executed":
                st.caption("این پیش‌نویس هنوز نتیجه رسمی ذخیره‌شده ندارد؛ آن را باز کنید و سناریو را اجرا کنید.")
            if actions[2].button("ایجاد نسخه جدید", key=f"workspace_version_{item.scenario_id}", width="stretch"):
                try: _new_version(item.scenario_id)
                except Exception: st.error("ایجاد نسخه جدید انجام نشد.")
            if mode == ScenarioType.FOCUS_BRANCH_ONLY.value and actions[3].button("حذف", key=f"ask_delete_{item.scenario_id}", width="stretch"):
                st.session_state["confirm_scenario_delete"] = item.scenario_id
                st.rerun()
            if st.session_state.get("confirm_scenario_delete") == item.scenario_id:
                st.warning("آیا از حذف این سناریوی ذخیره‌شده مطمئن هستید؟ این عملیات قابل بازگشت نیست.")
                confirm = st.columns(2)
                if confirm[0].button("بله، حذف شود", key=f"confirm_delete_{item.scenario_id}"):
                    try: _workspace_service().delete_scenario(item.scenario_id, item.row_version)
                    except (ScenarioPersistenceError, ValueError, OSError): st.error("حذف سناریو انجام نشد.")
                    else: st.session_state.pop("confirm_scenario_delete", None); st.rerun()
                if confirm[1].button("انصراف", key=f"cancel_delete_{item.scenario_id}"):
                    st.session_state.pop("confirm_scenario_delete", None); st.rerun()


if __name__ == "__main__":
    main()
