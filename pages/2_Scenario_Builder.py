"""Three-mode Persian RTL sensitivity workspace."""

from __future__ import annotations

import html
from pathlib import Path
import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from domain.scenario_contracts import ScenarioExecutionResult, ScenarioType
from engine.indicator_registry import INDICATOR_REGISTRY, PROFIT_LOSS_KEY
from engine.ranking_engine import BRANCH_ID, BRANCH_NAME, INDICATOR_TYPES, REGION, WEIGHTS
from engine.scenario_rule_engine import RuleOperation
from services.focus_branch import FocusBranchSource, resolve_focus_branch
from services.scenario_execution_service import ScenarioExecutionService, ScenarioRequestValidationError
from services.selection_scope import SelectionResolver, SelectionScope
from services.user_context import load_current_user
from services.factory import create_local_scenario_service
from services.multi_branch_workspace_service import MultiBranchWorkspaceService
from services.scenario_workspace_service import ScenarioWorkspaceService
from persistence.contracts import ConcurrencyError, ScenarioPersistenceError
from ui import initialize_session_state
from ui.components import render_empty_state
from ui.data_access import load_dashboard_data
from ui.formatters import (
    format_compact_number, format_editable_number, format_grade, format_managerial_number, format_percentage,
    format_persian_number, format_persian_percentage, format_rank, format_raw_input_value, format_raw_value,
    format_score, format_signed_persian_number, format_signed_persian_percentage,
    parse_formatted_number, parse_raw_input_value, persian_digits,
)
from ui.sensitivity_adapters import (
    build_focus_request, build_multi_request, build_target_comparison_request,
    preview_raw_operation, rank_change_presentation,
    focus_result_presentation,
    result_branch_options, select_official_branch_result, service_error_message,
    target_solution_comparison, unique_indicator_ids,
)
from ui.sensitivity_labels import (
    INDICATOR_TYPE_LABELS, OPERATION_LABELS, SCENARIO_TYPE_LABELS,
    SCOPE_LABELS,
)
from ui.sensitivity_components import (
    render_indicator_cards, render_process_timeline, render_summary_cards,
    render_value_comparison, render_wizard_steps,
)
from ui.sensitivity_state import (
    SESSION_HISTORY_KEY, SENSITIVITY_DRAFT_KEY,
    delete_bulk_rule, delete_manual_override,
    return_to_edit, set_focus_branch, set_multi_branch_selection,
    set_selected_indicators,
)
from ui.styles import apply_global_styles
from ui.navigation import activate_requested_scenario, branch_select_label, icon_svg
from ui.multi_branch_page import render_multi_branch_workspace

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "Data.xlsx"
PERIOD = "1404-04"
LOGGER = logging.getLogger(__name__)
OPERATIONS = tuple(OPERATION_LABELS)
SCOPES = tuple(SCOPE_LABELS)
LOCAL_ADMINISTRATIVE_TESTING_MODE = True


@st.cache_data(show_spinner="در حال بارگذاری و محاسبه اطلاعات مبنا...")
def load_baseline():
    return load_dashboard_data(DATA_FILE, PERIOD)


@st.cache_resource
def workspace_service() -> ScenarioWorkspaceService:
    return ScenarioWorkspaceService(create_local_scenario_service(ROOT))


@st.cache_resource
def multi_branch_workspace_service() -> MultiBranchWorkspaceService:
    return MultiBranchWorkspaceService(create_local_scenario_service(ROOT))


def _persistence_error(exc: Exception) -> None:
    if isinstance(exc, ConcurrencyError):
        st.session_state["sensitivity_persistence_conflict"] = True
        st.error("این سناریو پس از بازشدن شما توسط کاربر یا نشست دیگری تغییر کرده است. برای جلوگیری از بازنویسی اطلاعات، نسخه جدید را بارگذاری کنید.")
    elif isinstance(exc, (ScenarioPersistenceError, ValueError)):
        LOGGER.warning("Scenario persistence failure: %s", exc)
        st.error("ذخیره یا بارگذاری سناریو انجام نشد. لطفاً اطلاعات را بازبینی و دوباره تلاش کنید.")
    else:
        LOGGER.exception("Unexpected scenario persistence failure")
        st.error("عملیات ذخیره‌سازی با خطای پیش‌بینی‌نشده روبه‌رو شد.")


def _save_draft(draft, *, save_as_new: bool = False) -> None:
    try:
        workspace_service().save_draft(draft, save_as_new=save_as_new)
    except Exception as exc:
        _persistence_error(exc)
    else:
        st.session_state["sensitivity_persistence_conflict"] = False
        st.success("پیش‌نویس ذخیره شد")


def _save_execution(draft) -> None:
    first_save = not bool(dict(draft.get("persistence") or {}).get("scenario_id"))
    try:
        workspace_service().save_execution(draft)
    except Exception as exc:
        _persistence_error(exc)
    else:
        st.success("سناریو با موفقیت ذخیره شد." if first_save else "تغییرات سناریو با موفقیت ذخیره شد.")


def _reload_saved(draft, data) -> None:
    scenario_id = dict(draft.get("persistence") or {}).get("scenario_id")
    if not scenario_id:
        return
    try:
        loaded = workspace_service().load_scenario(
            scenario_id, branch_ids=data[BRANCH_ID].astype(str), periods=[PERIOD]
        )
    except Exception as exc:
        _persistence_error(exc)
    else:
        st.session_state[SENSITIVITY_DRAFT_KEY] = loaded.draft
        st.session_state["sensitivity_restore_warnings"] = list(loaded.warnings)
        st.session_state["sensitivity_persistence_conflict"] = False
        st.rerun()


def _branch_maps(data: pd.DataFrame) -> tuple[list[str], dict[str, str]]:
    ids = data[BRANCH_ID].astype(str).tolist()
    names = data.assign(**{BRANCH_ID: data[BRANCH_ID].astype(str)}).set_index(BRANCH_ID)[BRANCH_NAME].astype(str).to_dict()
    return ids, names


def _branch_label(branch_id: str, names: dict[str, str]) -> str:
    return branch_select_label(str(branch_id), names)


def _scenario_context(draft: dict, names: dict[str, str] | None = None) -> str:
    name = str(draft.get("scenario_name") or "").strip()
    if name:
        return f"نام سناریو: {name}"
    branch_id = draft.get("focus_branch_id")
    if branch_id and names:
        return f"شعبه انتخاب‌شده: {_branch_label(str(branch_id), names)}"
    if branch_id:
        return f"کد شعبه انتخاب‌شده: {branch_id}"
    return SCENARIO_TYPE_LABELS[draft["scenario_type"]]


def _selected_branch_banner(branch_id: str, names: dict[str, str]) -> None:
    branch_name = names.get(str(branch_id), "شعبه")
    code = str(branch_id).strip()
    code_badge = (
        f'<span class="selected-branch-code">کد شعبه: <bdi>{html.escape(persian_digits(branch_id))}</bdi></span>'
        if code else ""
    )
    st.markdown(
        '<div class="selected-branch-banner" data-selected-branch-banner="true">'
        f'<span class="selected-branch-icon">{icon_svg("bank")}</span>'
        '<div class="selected-branch-text"><small>شعبه انتخاب‌شده</small>'
        f'<strong>{html.escape(branch_name)}</strong></div>'
        f'{code_badge}</div>',
        unsafe_allow_html=True,
    )


def _step_three_header(branch_id: str, names: dict[str, str]) -> None:
    st.markdown(
        '<section class="change-step-header" data-change-step-header="true">'
        '<h2>تعریف تغییرات</h2>'
        '<p>میزان و نوع تغییر هر شاخص را برای سناریوی انتخاب‌شده مشخص کنید.</p>'
        '</section>',
        unsafe_allow_html=True,
    )
    _selected_branch_banner(branch_id, names)


def _indicator_edit_header(indicator_id: str, title: str, current: object) -> str:
    return (
        '<div class="scenario-edit-card" data-scenario-edit-card="true" data-self-contained-card="true">'
        '<header><div class="indicator-edit-title">'
        f'<span class="indicator-edit-icon">{icon_svg("target")}</span>'
        f'<h3>{html.escape(title)}</h3></div>'
        '<div class="indicator-base-value"><span>مقدار پایه</span>'
        f'<strong class="numeric-fa" dir="rtl">{html.escape(format_persian_number(current, 0))}</strong></div>'
        '</header></div>'
    )


def _raw_text_input(container, label: str, value: object, key: str, **kwargs) -> str:
    return container.text_input(label, value=format_raw_input_value(value), key=key, **kwargs)


def _focus_row(data: pd.DataFrame, outputs, branch_id: str) -> tuple[pd.Series, pd.Series]:
    raw = data.loc[data[BRANCH_ID].astype(str).eq(str(branch_id))].iloc[0]
    result = outputs.final_result.loc[outputs.final_result[BRANCH_ID].astype(str).eq(str(branch_id))].iloc[0]
    return raw, result


def _steps(mode: ScenarioType) -> tuple[str, ...]:
    if mode is ScenarioType.FOCUS_BRANCH_ONLY:
        return ("انتخاب شعبه", "انتخاب شاخص‌ها", "تعریف تغییرات", "بازبینی و اجرا")
    if mode is ScenarioType.MULTI_BRANCH:
        return ("انتخاب شعب", "تعریف قواعد عمومی", "تغییرات اختصاصی شعب", "بازبینی و اجرا")
    return ("تعریف هدف و انتخاب شاخص‌ها", "نتایج سناریوی رتبه هدف")


def _wizard_header(draft: dict) -> None:
    render_wizard_steps(_steps(draft["scenario_type"]), draft["current_step"])


def _scenario_page_header(mode: ScenarioType) -> None:
    st.markdown(
        '<header class="scenario-builder-header">'
        f'<span class="scenario-builder-header-icon">{icon_svg("bank")}</span>'
        '<div>'
        f'<h1>{html.escape(SCENARIO_TYPE_LABELS[mode])}</h1>'
        '<p>تعریف سناریو و اجرای آن با مدل رسمی درجه‌بندی</p>'
        '</div></header>',
        unsafe_allow_html=True,
    )


def _scenario_name_panel(draft: dict, data) -> None:
    persistence = dict(draft.get("persistence") or {})
    dirty = workspace_service().has_unsaved_changes(draft)
    status_text = "تغییرات ذخیره‌نشده وجود دارد" if dirty else (
        "پیش‌نویس ذخیره‌شده" if persistence.get("status") == "draft" else
        "نتیجه ذخیره‌شده" if persistence.get("status") == "executed" else "ذخیره‌نشده"
    )
    with st.container(border=True):
        st.markdown('<div class="scenario-name-panel" data-scenario-name-panel="true">', unsafe_allow_html=True)
        columns = st.columns([4.5, 1.35, 1.15])
        name = columns[0].text_input(
            "نام سناریو",
            value=str(draft.get("scenario_name") or ""),
            key="sensitivity_scenario_name",
        )
        columns[1].markdown(
            f'<span class="scenario-save-status"><b aria-hidden="true"></b>{html.escape(status_text)}</span>',
            unsafe_allow_html=True,
        )
        if columns[2].button("ذخیره پیش‌نویس", width="stretch"):
            _save_draft(draft)
        draft["scenario_name"] = name
        st.markdown('</div>', unsafe_allow_html=True)
    if st.session_state.get("sensitivity_persistence_conflict"):
        conflict_actions = st.columns(2)
        if conflict_actions[0].button("بارگذاری آخرین نسخه", width="stretch"):
            _reload_saved(draft, data)
        if conflict_actions[1].button("ذخیره به‌عنوان نسخه جدید", width="stretch"):
            _save_draft(draft, save_as_new=True)


def _branch_summary(data, outputs, branch_id: str) -> None:
    raw, result = _focus_row(data, outputs, branch_id)
    cards = (
        ("رتبه فعلی", format_persian_number(result["rank"], decimals=0), "target"),
        ("امتیاز فعلی", format_persian_number(result["final_score"], decimals=1), "folder"),
        ("درجه فعلی", format_grade(result["grade"]), "bank"),
    )
    card_markup = "".join(
        '<article class="branch-info-card">'
        '<div class="branch-info-content">'
        f'<span>{html.escape(label)}</span>'
        f'<strong class="numeric-fa">{html.escape(str(value))}</strong>'
        '</div>'
        f'<span class="branch-info-icon">{icon_svg(icon)}</span></article>'
        for label, value, icon in cards
    )
    st.markdown(
        '<section class="branch-summary-panel">'
        f'<header><h3>{html.escape(str(raw[BRANCH_NAME]))}</h3>'
        f'<p>کد شعبه: <bdi>{html.escape(persian_digits(raw[BRANCH_ID]))}</bdi> | '
        f'منطقه: {html.escape(str(raw[REGION]))}</p></header>'
        f'<div class="branch-info-grid">{card_markup}</div></section>',
        unsafe_allow_html=True,
    )


def _select_focus(draft, data, outputs, user) -> None:
    ids, names = _branch_maps(data)
    if draft["scenario_type"] is ScenarioType.TARGET_RANK:
        current = draft.get("focus_branch_id") if draft.get("focus_branch_id") in ids else None
        index = ids.index(current) + 1 if current in ids else 0
        chosen = st.selectbox(
            "انتخاب شعبه هدف",
            [None, *ids],
            index=index,
            format_func=lambda item: "انتخاب شعبه" if item is None else _branch_label(item, names),
            key="target_rank_branch_selector",
            help="شعبه هدف را از کل جامعه رسمی شعب انتخاب کنید.",
        )
        set_focus_branch(draft, chosen, FocusBranchSource.USER_SELECTED_BRANCH.value if chosen else None)
        if user.branch_id and str(user.branch_id) in ids:
            st.caption(f"شعبه منتسب به کاربر: {_branch_label(str(user.branch_id), names)}")
        if not draft.get("focus_branch_id"):
            st.markdown(
                '<section class="target-rank-definition-panel">'
                '<header><h2>تعریف هدف</h2><p>برای شروع، یک شعبه هدف از فهرست رسمی شعب انتخاب کنید.</p></header>'
                '</section>',
                unsafe_allow_html=True,
            )
            return
        raw, result = _focus_row(data, outputs, str(draft["focus_branch_id"]))
        baseline_rank = int(result["rank"])
        valid_ranks = list(range(1, baseline_rank))
        if not valid_ranks:
            st.warning("این شعبه هم‌اکنون بهترین رتبه را دارد و رتبه هدف بهتری برای آن قابل انتخاب نیست.")
            return
        stored_target = draft["target_rank_request"].get("target_rank")
        target_index = valid_ranks.index(int(stored_target)) if stored_target in valid_ranks else max(0, len(valid_ranks) - 1)
        target = st.selectbox(
            "رتبه هدف",
            valid_ranks,
            index=target_index,
            format_func=lambda item: f"رتبه {persian_digits(item)}",
            key=f"target_rank_goal_{draft['focus_branch_id']}",
            help="رتبه هدف باید بهتر از رتبه فعلی شعبه باشد.",
        )
        if draft["target_rank_request"].get("target_rank") != int(target):
            draft["target_rank_request"]["target_rank"] = int(target)
            draft["target_comparison_result"] = None
            draft["target_solution"] = None
            draft["target_execution_completed"] = False
            draft["show_result"] = False
        gap = float(result["final_score"]) - float(
            outputs.final_result.loc[outputs.final_result["rank"].eq(int(target)), "final_score"].iloc[0]
        ) if int(target) in set(outputs.final_result["rank"].astype(int)) else None
        scenario_name = str(draft.get("scenario_name") or "سناریوی رتبه هدف")
        st.markdown(
            '<section class="target-rank-definition-panel">'
            '<div class="target-rank-branch-selector"><small>شعبه هدف</small>'
            f'<strong>{html.escape(str(raw[BRANCH_NAME]))}</strong><span>کد شعبه: <bdi>{html.escape(persian_digits(raw[BRANCH_ID]))}</bdi></span>'
            f'<span>نام سناریو: {html.escape(scenario_name)}</span></div>'
            '<div class="target-rank-current-state">'
            f'<span><small>رتبه فعلی</small><b>{html.escape(persian_digits(baseline_rank))}</b></span>'
            f'<span><small>امتیاز فعلی</small><b>{html.escape(persian_digits(format_score(result["final_score"])))}</b></span>'
            f'<span><small>درجه فعلی</small><b>{html.escape(format_grade(result["grade"]))}</b></span></div>'
            '<div class="target-rank-target-control"><small>رتبه هدف</small>'
            f'<strong>{html.escape(persian_digits(target))}</strong>'
            f'<span>بهبود موردنیاز: {html.escape(persian_digits(baseline_rank - int(target)))} رتبه</span>'
            f'<span>شکاف امتیاز تخمینی: {html.escape(persian_digits(format_score(abs(gap)))) if gap is not None else "—"}</span></div>'
            '</section>',
            unsafe_allow_html=True,
        )
        return
    if draft["scenario_type"] is ScenarioType.MULTI_BRANCH:
        defaults = [item for item in draft.get("selected_branch_ids", []) if item in ids]
        if user.branch_id and str(user.branch_id) in ids and str(user.branch_id) not in defaults:
            defaults.insert(0, str(user.branch_id))
        selected = st.multiselect(
            "انتخاب چند شعبه", ids, default=defaults,
            format_func=lambda item: _branch_label(item, names), key="sensitivity_multi_branches",
        )
        source = (FocusBranchSource.ASSIGNED_USER_BRANCH.value
                  if user.branch_id and selected and selected[0] == str(user.branch_id)
                  else FocusBranchSource.USER_SELECTED_BRANCH.value)
        set_multi_branch_selection(draft, selected, focus_source=source)
        if selected:
            _selected_branch_banner(selected[0], names)
            _branch_summary(data, outputs, selected[0])
        return
    if draft["scenario_type"] is ScenarioType.FOCUS_BRANCH_ONLY and LOCAL_ADMINISTRATIVE_TESTING_MODE:
        with st.container(border=True):
            st.markdown(
                '<section class="branch-step-panel" data-branch-step="focus-step-1">'
                '<header><h2>انتخاب شعبه</h2><p>شعبه مبنای سناریوی شعبه‌محور را از فهرست داده‌های جاری انتخاب کنید.</p></header>'
                '</section>',
                unsafe_allow_html=True,
            )
            current = draft.get("focus_branch_id") if draft.get("entry_source") == "saved" else None
            index = ids.index(current) + 1 if current in ids else 0
            chosen = st.selectbox(
                "جست‌وجو و انتخاب شعبه", [None, *ids], index=index,
                format_func=lambda item: branch_select_label(item, names),
                key="sensitivity_focus_branch",
                help="در حالت آزمون مدیریتی، همه شعب فعال قابل انتخاب‌اند.",
            )
            set_focus_branch(draft, chosen, FocusBranchSource.USER_SELECTED_BRANCH.value if chosen else None)
            if draft.get("focus_branch_id"):
                _selected_branch_banner(str(draft["focus_branch_id"]), names)
            st.markdown(
                '<div class="branch-info-alert"><span aria-hidden="true">i</span>'
                '<p>حالت آزمون مدیریتی فعال است؛ محدودیت شعبه تخصیص‌یافته کاربر محلی اعمال نمی‌شود.</p></div>',
                unsafe_allow_html=True,
            )
            if draft.get("focus_branch_id"):
                _branch_summary(data, outputs, str(draft["focus_branch_id"]))
        return
    if user.branch_id:
        try:
            focus = resolve_focus_branch(user, data)
        except ValueError as exc:
            st.error(str(exc)); return
        set_focus_branch(draft, focus.branch_id, focus.source.value)
        _selected_branch_banner(focus.branch_id, names)
        st.info(f"شعبه محوری بر اساس شعبه تخصیص‌یافته کاربر انتخاب شد: {_branch_label(focus.branch_id, names)}")
    else:
        current = draft.get("focus_branch_id")
        index = ids.index(current) + 1 if current in ids else 0
        chosen = st.selectbox("جست‌وجوی نام یا کد شعبه", [None, *ids], index=index,
                              format_func=lambda item: "انتخاب شعبه" if item is None else _branch_label(item, names),
                              key="sensitivity_focus_branch")
        set_focus_branch(draft, chosen, FocusBranchSource.USER_SELECTED_BRANCH.value if chosen else None)
    if draft.get("focus_branch_id"):
        _selected_branch_banner(str(draft["focus_branch_id"]), names)
        _branch_summary(data, outputs, draft["focus_branch_id"])
        if draft["scenario_type"] is ScenarioType.TARGET_RANK:
            _, result = _focus_row(data, outputs, draft["focus_branch_id"])
            baseline_rank = int(result["rank"])
            target = st.number_input("رتبه هدف", min_value=1, max_value=len(data),
                                     value=int(draft["target_rank_request"].get("target_rank", max(1, baseline_rank - 1))), step=1,
                                     key=f"target_rank_goal_{draft['focus_branch_id']}")
            if draft["target_rank_request"].get("target_rank") != int(target):
                draft["target_rank_request"]["target_rank"] = int(target)
                draft["target_comparison_result"] = None
                draft["target_solution"] = None
                draft["show_result"] = False
            if target >= baseline_rank:
                st.info("شعبه هم‌اکنون رتبه درخواستی را دارد یا از آن بهتر است؛ تغییری لازم نیست.")


def _indicator_picker(draft, data, outputs) -> None:
    branch_id = draft["focus_branch_id"]
    raw, _ = _focus_row(data, outputs, branch_id)
    selected = list(draft.get("selected_indicator_ids", []))
    if draft["scenario_type"] is ScenarioType.TARGET_RANK:
        st.markdown(
            '<section class="target-rank-indicator-explainer">'
            '<header><h2>شاخص‌های مسیر منتخب خود را مشخص کنید</h2>'
            '<p>سامانه دو مسیر را به‌صورت هم‌زمان محاسبه می‌کند: مسیر متوازن با استفاده از هر ۸ شاخص رسمی مدل و مسیر منتخب با استفاده از شاخص‌هایی که شما انتخاب می‌کنید.</p>'
            '<p>انتخاب شاخص به معنی تعیین درصد تغییر نیست. سامانه مقدار تغییر لازم را با مدل رسمی محاسبه می‌کند. شاخص‌هایی را انتخاب کنید که تمرکز بر بهبود آن‌ها برای شعبه امکان‌پذیرتر است.</p></header>'
            '<div><em>مسیر متوازن: هر ۸ شاخص</em><em>مسیر منتخب: انتخاب کاربر</em><span>حداقل یک شاخص برای مسیر منتخب انتخاب کنید.</span></div>'
            '</section>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("یک یا چند شاخص را انتخاب کنید. هر شاخص فقط یک‌بار قابل انتخاب است.")
    for row_start in range(0, len(INDICATOR_REGISTRY), 4):
        for column, indicator_id in zip(st.columns(4), list(INDICATOR_REGISTRY)[row_start:row_start + 4]):
            definition = INDICATOR_REGISTRY[indicator_id]
            selected_class = " selected" if indicator_id in selected else ""
            with column, st.container(border=True):
                st.markdown(
                    f'<span class="indicator-card-anchor{selected_class}" data-indicator-card="{html.escape(indicator_id)}" data-self-contained-card="true"></span>',
                    unsafe_allow_html=True,
                )
                checked = st.checkbox(definition.display_name, value=indicator_id in selected,
                                      key=f"select_{draft['scenario_type'].value}_{branch_id}_{indicator_id}")
                st.markdown(
                    '<div class="indicator-picker-meta">'
                    f'<span>مقدار پایه <b class="numeric-fa">{html.escape(format_persian_number(raw[indicator_id], decimals=0))}</b></span>'
                    f'<span class="weight">وزن رسمی <b class="numeric-fa">{html.escape(format_persian_percentage(WEIGHTS[indicator_id] * 100, 0))}</b></span>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                if draft["scenario_type"] is ScenarioType.TARGET_RANK:
                    st.caption(f"نوع: {INDICATOR_TYPE_LABELS.get(INDICATOR_TYPES[indicator_id], 'شاخص مدل')}")
                if checked and indicator_id not in selected: selected.append(indicator_id)
                if not checked and indicator_id in selected: selected.remove(indicator_id)
    try:
        set_selected_indicators(draft, list(unique_indicator_ids(selected)))
    except ValueError as exc:
        st.error(str(exc))
    if draft["scenario_type"] is ScenarioType.TARGET_RANK:
        selected_names = "، ".join(INDICATOR_REGISTRY[item].display_name for item in draft.get("selected_indicator_ids", [])) or "هنوز شاخصی انتخاب نشده است"
        status = "آماده اجرا" if draft.get("selected_indicator_ids") else "حداقل یک شاخص انتخاب کنید"
        chips = "".join(
            f'<em>{html.escape(INDICATOR_REGISTRY[item].display_name)}</em>'
            for item in draft.get("selected_indicator_ids", [])
        ) or '<em>بدون انتخاب</em>'
        st.markdown(
            '<section class="target-rank-selection-summary">'
            f'<strong>{html.escape(persian_digits(len(draft.get("selected_indicator_ids", []))))} شاخص انتخاب شده</strong>'
            f'<div title="{html.escape(selected_names)}">{chips}</div>'
            f'<span>{html.escape(status)}</span>'
            '</section>',
            unsafe_allow_html=True,
        )


def _focus_changes(draft, data) -> None:
    raw = data.loc[data[BRANCH_ID].astype(str).eq(str(draft["focus_branch_id"]))].iloc[0]
    names = _branch_maps(data)[1]
    _step_three_header(str(draft["focus_branch_id"]), names)
    selected_indicators = list(draft["selected_indicator_ids"])
    for row_start in range(0, len(selected_indicators), 2):
        for column, indicator_id in zip(st.columns(2), selected_indicators[row_start:row_start + 2]):
            definition = INDICATOR_REGISTRY[indicator_id]
            saved = draft["focus_changes"].get(indicator_id, {})
            with column, st.container(border=True):
                st.markdown(
                    _indicator_edit_header(indicator_id, definition.display_name, raw[indicator_id]),
                    unsafe_allow_html=True,
                )
                control = st.container()
                st.markdown('<div class="scenario-edit-controls">', unsafe_allow_html=True)
                columns = control.columns([1.15, 1, 1.2])
                operation = columns[0].selectbox("نوع تغییر", OPERATIONS,
                    index=OPERATIONS.index(RuleOperation(saved.get("operation", RuleOperation.PERCENT_CHANGE.value))),
                    format_func=OPERATION_LABELS.get, key=f"focus_op_{indicator_id}")
                saved_value = float(saved.get("value", 0.0))
                if operation is not RuleOperation.SET_VALUE:
                    direction = columns[1].radio(
                        "جهت تغییر", (1, -1), index=1 if saved_value < 0 else 0,
                        format_func=lambda item: "افزایش" if item == 1 else "کاهش",
                        horizontal=True, key=f"focus_direction_{indicator_id}_{operation.value}",
                    )
                    if direction < 0:
                        columns[1].markdown('<span class="direction-decrease-active"></span>', unsafe_allow_html=True)
                    else:
                        columns[1].markdown('<span class="direction-increase-active"></span>', unsafe_allow_html=True)
                    input_label = "مقدار تغییر ٪" if operation is RuleOperation.PERCENT_CHANGE else "مقدار تغییر"
                    formatter = format_editable_number if operation is RuleOperation.PERCENT_CHANGE else format_raw_input_value
                    raw_text = columns[2].text_input(
                        input_label, value=formatter(abs(saved_value)),
                        key=f"focus_value_{indicator_id}_{operation.value}",
                        help="عدد را می‌توانید با جداکننده هزارگان وارد کنید.",
                    )
                else:
                    direction = 1
                    columns[1].caption("مقدار واردشده مستقیماً جایگزین مقدار فعلی می‌شود.")
                    raw_text = _raw_text_input(
                        columns[2],
                        "مقدار نهایی", value=saved_value,
                        key=f"focus_value_{indicator_id}_{operation.value}",
                        help="عدد را می‌توانید با جداکننده هزارگان وارد کنید.",
                    )
                st.markdown('</div>', unsafe_allow_html=True)
                try:
                    entered = (
                        parse_formatted_number(raw_text)
                        if operation is RuleOperation.PERCENT_CHANGE
                        else parse_raw_input_value(raw_text)
                    )
                    value = entered if operation is RuleOperation.SET_VALUE else abs(entered) * direction
                    preview = preview_raw_operation(raw[indicator_id], operation, value, indicator_id)
                except ValueError as exc:
                    st.error(str(exc)); draft["focus_changes"].pop(indicator_id, None)
                else:
                    render_value_comparison(float(raw[indicator_id]), preview)
                    draft["focus_changes"][indicator_id] = {"operation": operation.value, "value": float(value), "preview": preview}
                if indicator_id == PROFIT_LOSS_KEY and float(raw[indicator_id]) < 0 and operation is RuleOperation.PERCENT_CHANGE:
                    st.info("برای مقدار منفی سود و زیان، کاهش درصدی مقدار را به صفر نزدیک‌تر می‌کند؛ افزایش درصدی قدرمطلق زیان را بیشتر می‌کند.")


def _add_bulk_rule(draft, data) -> None:
    ids, names = _branch_maps(data); regions = sorted(data[REGION].astype(str).unique())
    with st.form("bulk_rule_form", clear_on_submit=False):
        columns = st.columns(4)
        scope = columns[0].selectbox("دامنه", SCOPES, format_func=SCOPE_LABELS.get)
        indicator = columns[1].selectbox("شاخص", list(INDICATOR_REGISTRY), format_func=lambda key: INDICATOR_REGISTRY[key].display_name)
        operation = columns[2].selectbox("نوع تغییر", OPERATIONS, format_func=OPERATION_LABELS.get)
        default_value = draft.get("_bulk_rule_value", 0.0)
        value_text = _raw_text_input(columns[3], "مقدار", default_value, key="bulk_rule_value")
        defaults = [item for item in draft.get("selected_branch_ids", []) if item in ids]
        selected_ids = st.multiselect("شعب منتخب", ids, default=defaults, format_func=lambda item: _branch_label(item, names), disabled=scope is not SelectionScope.SELECTED_BRANCHES)
        selected_regions = st.multiselect("مناطق منتخب", regions, disabled=scope is not SelectionScope.SELECTED_REGIONS)
        submitted = st.form_submit_button("افزودن قاعده عمومی", type="primary")
    if submitted:
        if scope is SelectionScope.SELECTED_BRANCHES and not selected_ids: st.error("حداقل یک شعبه را انتخاب کنید.")
        elif scope is SelectionScope.SELECTED_REGIONS and not selected_regions: st.error("حداقل یک منطقه را انتخاب کنید.")
        else:
            try:
                value = parse_raw_input_value(value_text)
            except ValueError as exc:
                st.error(str(exc)); return
            draft["bulk_rules"].append({"target_scope": scope.value, "indicator_id": indicator, "operation": operation.value,
                                         "value": float(value), "selected_branch_ids": list(selected_ids), "selected_regions": list(selected_regions)})
    for index, rule in enumerate(list(draft["bulk_rules"])):
        scope = SelectionScope(rule["target_scope"])
        try:
            targets = SelectionResolver.resolve(scope, data, load_current_user(ROOT / "config/local_user.json"),
                selected_branch_ids=rule.get("selected_branch_ids"), selected_regions=rule.get("selected_regions"))
        except ValueError: targets = []
        with st.container(border=True):
            st.write(f"{SCOPE_LABELS[scope]} | {INDICATOR_REGISTRY[rule['indicator_id']].display_name} | {OPERATION_LABELS[RuleOperation(rule['operation'])]}: {format_raw_value(rule['value'])}")
            st.caption(f"منبع مقدار: قاعده عمومی | تعداد شعب هدف: {len(targets)}")
            if st.button("حذف", key=f"delete_bulk_{index}"):
                delete_bulk_rule(draft, index); st.rerun()


def _add_override(draft, data) -> None:
    ids, names = _branch_maps(data)
    st.info("تغییر اختصاصی شعبه بر قاعده عمومی همان شعبه و شاخص اولویت دارد.")
    edit_index = draft.get("override_edit_index")
    editing = draft["manual_overrides"][edit_index] if isinstance(edit_index, int) and edit_index < len(draft["manual_overrides"]) else None
    with st.form("override_form"):
        columns = st.columns(4)
        branch = columns[0].selectbox("شعبه", ids, index=ids.index(editing["branch_id"]) if editing else 0, format_func=lambda item: _branch_label(item, names))
        indicator_ids = list(INDICATOR_REGISTRY)
        indicator = columns[1].selectbox("شاخص", indicator_ids, index=indicator_ids.index(editing["indicator_id"]) if editing else 0, format_func=lambda key: INDICATOR_REGISTRY[key].display_name)
        operation = columns[2].selectbox("نوع تغییر", OPERATIONS, index=OPERATIONS.index(RuleOperation(editing["operation"])) if editing else 0, format_func=OPERATION_LABELS.get)
        value_text = _raw_text_input(columns[3], "مقدار", float(editing["value"]) if editing else 0.0, key="override_value")
        submitted = st.form_submit_button("ثبت ویرایش" if editing else "افزودن تغییر اختصاصی", type="primary")
    if submitted:
        key = (branch, indicator)
        occupied = {(row["branch_id"], row["indicator_id"]) for i, row in enumerate(draft["manual_overrides"]) if i != edit_index}
        if key in occupied:
            st.error("برای این شعبه و شاخص قبلاً تغییر اختصاصی ثبت شده است.")
        else:
            try:
                value = parse_raw_input_value(value_text)
            except ValueError as exc:
                st.error(str(exc)); return
            row = {"branch_id": branch, "indicator_id": indicator, "operation": operation.value, "value": float(value)}
            if editing: draft["manual_overrides"][edit_index] = row; draft.pop("override_edit_index", None)
            else: draft["manual_overrides"].append(row)
    for index, row in enumerate(list(draft["manual_overrides"])):
        with st.container(border=True):
            st.write(f"{_branch_label(row['branch_id'], names)} | {INDICATOR_REGISTRY[row['indicator_id']].display_name} | {OPERATION_LABELS[RuleOperation(row['operation'])]}: {format_raw_value(row['value'])}")
            st.caption("منبع مقدار: تغییر اختصاصی؛ با بازنشانی، مقدار از قاعده عمومی یا داده مبنا به ارث می‌رسد.")
            actions = st.columns(2)
            if actions[0].button("ویرایش", key=f"edit_override_{index}"):
                draft["override_edit_index"] = index; st.rerun()
            if actions[1].button("بازنشانی به قاعده عمومی یا مبنا", key=f"delete_override_{index}"):
                delete_manual_override(draft, index); draft.pop("override_edit_index", None); st.rerun()


def _review(draft, data) -> None:
    ids, names = _branch_maps(data); focus = draft["focus_branch_id"]
    changed_count = len(draft["focus_changes"]) if draft["scenario_type"] is ScenarioType.FOCUS_BRANCH_ONLY else len(draft["bulk_rules"]) + len(draft["manual_overrides"])
    persistence = dict(draft.get("persistence") or {})
    status_text = (
        "پیش‌نویس ذخیره‌شده" if persistence.get("status") == "draft" else
        "نتیجه ذخیره‌شده" if persistence.get("status") == "executed" else "ذخیره نشده"
    )
    st.markdown(
        '<section class="scenario-review-summary" data-scenario-review="summary">'
        f'<div class="branch"><span class="review-summary-icon">{icon_svg("bank")}</span><section><small>شعبه انتخاب‌شده</small>'
        f'<strong>{html.escape(names.get(str(focus), str(focus)))}</strong>'
        f'<em>کد شعبه: <bdi>{html.escape(persian_digits(focus))}</bdi></em></section></div>'
        f'<div class="changes"><span class="review-summary-icon">{icon_svg("target")}</span><section><small>تغییرات سناریو</small>'
        f'<strong class="numeric-fa">{html.escape(persian_digits(changed_count))} شاخص</strong><em>بر پایه تغییرات ثبت‌شده</em></section></div>'
        f'<div class="scenario"><span class="review-summary-icon">{icon_svg("folder")}</span><section><small>نام سناریو</small>'
        f'<strong>{html.escape(str(draft.get("scenario_name") or "بدون نام"))}</strong><em>{html.escape(status_text)}</em></section></div>'
        '</section>',
        unsafe_allow_html=True,
    )
    if draft["scenario_type"] is ScenarioType.FOCUS_BRANCH_ONLY:
        rows = []
        cards = []
        for key, value in draft["focus_changes"].items():
            current = float(data.loc[data[BRANCH_ID].astype(str).eq(focus), key].iloc[0])
            preview = float(value["preview"])
            difference = preview - current
            percent = None if current == 0 else difference / current * 100
            tone = "success" if difference > 0 else "danger" if difference < 0 else "neutral"
            rows.append({"شاخص": INDICATOR_REGISTRY[key].display_name, "مقدار فعلی": format_persian_number(current, 0),
                         "نوع تغییر": OPERATION_LABELS[RuleOperation(value["operation"])], "مقدار واردشده": format_persian_number(value["value"], 0), "مقدار جدید سناریو": format_persian_number(preview, 0),
                         "تغییر مطلق": format_persian_number(difference, 0), "تغییر درصدی": "—" if percent is None else format_persian_percentage(percent, 1)})
            cards.append(
                f'<article class="review-change-card {tone}"><header><h3>{html.escape(INDICATOR_REGISTRY[key].display_name)}</h3>'
                f'<span class="change-mode-badge">{html.escape(OPERATION_LABELS[RuleOperation(value["operation"])])}: <bdi>{html.escape(format_persian_number(value["value"], 0) if RuleOperation(value["operation"]) is not RuleOperation.PERCENT_CHANGE else format_persian_percentage(value["value"], 1))}</bdi></span></header>'
                '<div class="review-flow">'
                f'<div><span>مقدار فعلی</span><strong class="numeric-fa">{html.escape(format_persian_number(current, 0))}</strong></div>'
                '<b aria-hidden="true">←</b>'
                f'<div><span>مقدار جدید سناریو</span><strong class="numeric-fa">{html.escape(format_persian_number(preview, 0))}</strong></div></div>'
                '<div class="review-result-strip">'
                f'<span class="diff"><b aria-hidden="true">{"↑" if difference > 0 else "↓" if difference < 0 else "•"}</b> تغییر مطلق: <strong class="numeric-fa">{html.escape(format_signed_persian_number(difference, 0))}</strong></span>'
                f'<span class="diff">تغییر درصدی: <strong class="numeric-fa">{html.escape("—" if percent is None else format_persian_percentage(percent, 1))}</strong></span>'
                '</div></article>'
            )
        st.markdown(f'<section class="review-card-grid">{"".join(cards)}</section>', unsafe_allow_html=True)
        with st.expander("نمایش جدولی", expanded=False):
            st.dataframe(rows, width="stretch", hide_index=True)
        st.info("مقادیر خام همه شعب دیگر بدون تغییر باقی می‌ماند.")
    else:
        targeted: set[str] = set()
        user = load_current_user(ROOT / "config/local_user.json")
        for rule in draft["bulk_rules"]:
            try:
                targeted.update(SelectionResolver.resolve(SelectionScope(rule["target_scope"]), data, user,
                    selected_branch_ids=rule.get("selected_branch_ids"), selected_regions=rule.get("selected_regions")))
            except ValueError:
                pass
        targeted.update(str(row["branch_id"]) for row in draft["manual_overrides"])
        metrics = st.columns(4); metrics[0].metric("تعداد قواعد عمومی", len(draft["bulk_rules"])); metrics[1].metric("تعداد تغییرات اختصاصی", len(draft["manual_overrides"])); metrics[2].metric("تعداد شعب هدف", len(targeted)); metrics[3].metric("شعبه محوری", names.get(focus, focus))
        render_process_timeline(("داده پایه", "قواعد عمومی", "تغییرات اختصاصی", "اجرای مدل رسمی"))


def _execute(draft, data) -> None:
    try:
        request = build_focus_request(draft) if draft["scenario_type"] is ScenarioType.FOCUS_BRANCH_ONLY else build_multi_request(draft)
        with st.spinner("در حال اجرای مدل رسمی درجه‌بندی..."):
            result = ScenarioExecutionService().execute(request, data)
    except ScenarioRequestValidationError as exc:
        st.error(service_error_message(str(exc)))
    except (ValueError, KeyError) as exc:
        st.error(str(exc))
    except Exception:
        LOGGER.exception("Unexpected sensitivity scenario execution failure")
        st.error("اجرای سناریو با خطای پیش‌بینی‌نشده روبه‌رو شد. لطفاً دوباره تلاش کنید.")
    else:
        draft["execution_result"] = result; draft["show_result"] = True
        st.session_state[SESSION_HISTORY_KEY].append({"نام سناریو": request.scenario_name, "نوع": SCENARIO_TYPE_LABELS[request.scenario_type], "شعبه محوری": request.focus_branch_id})
        st.rerun()


def _render_result_actions(draft) -> None:
    persistence = dict(draft.get("persistence") or {})
    existing = bool(persistence.get("scenario_id"))
    dirty = workspace_service().has_unsaved_changes(draft) if existing else True
    with st.container(border=True):
        st.markdown('<div class="result-action-title">اقدامات سناریو</div>', unsafe_allow_html=True)
        actions = st.columns(3)
        if existing:
            if actions[0].button("بروزرسانی همین سناریو", type="primary", width="stretch"):
                if not dirty:
                    st.info("این سناریو نسبت به آخرین نسخه ذخیره‌شده تغییری ندارد.")
                else:
                    _save_execution(draft)
        else:
            if actions[0].button("ذخیره نتیجه", type="primary", width="stretch"):
                _save_execution(draft)
        if actions[1].button("بازگشت و ویرایش", width="stretch"):
            return_to_edit(draft); st.rerun()


def _result_actions_bar(draft) -> None:
    persistence = dict(draft.get("persistence") or {})
    existing = bool(persistence.get("scenario_id"))
    dirty = workspace_service().has_unsaved_changes(draft) if existing else True
    st.markdown('<div class="results-action-bar" data-result-actions="true"></div>', unsafe_allow_html=True)
    actions = st.columns([1.25, 1.25, 5.5])
    primary_label = "بروزرسانی همین سناریو" if existing else "ذخیره نتیجه"
    if actions[0].button(primary_label, type="primary", width="stretch"):
        if existing and not dirty:
            st.info("این سناریو نسبت به آخرین نسخه ذخیره‌شده تغییری ندارد.")
        else:
            _save_execution(draft)
    if actions[1].button("بازگشت و ویرایش", width="stretch"):
        return_to_edit(draft); st.rerun()


def _rank_tone(value: int | float) -> str:
    return "success" if value > 0 else "danger" if value < 0 else "neutral"


def _score_tone(value: int | float) -> str:
    return "success" if value > 0 else "danger" if value < 0 else "neutral"


def _movement_icon(value: int | float) -> str:
    return "↗" if value > 0 else "↘" if value < 0 else "−"


def _rank_movement_text(value: int | float) -> str:
    movement = int(value)
    if movement > 0:
        return f"{format_persian_number(movement, 0)} رتبه صعود"
    if movement < 0:
        return f"{format_persian_number(abs(movement), 0)} رتبه نزول"
    return "بدون تغییر رتبه"


def _result_context_html(draft, result, comparison, names: dict[str, str]) -> str:
    branch_id = str(comparison.branch_id)
    changed_count = sum(1 for item in comparison.indicator_comparisons if abs(float(item.get("raw_value_change", 0.0))) > 1e-9)
    chips = [
        f'<strong>{html.escape(names.get(branch_id, branch_id))}</strong>',
        f'<span>کد شعبه: <bdi>{html.escape(persian_digits(branch_id))}</bdi></span>',
    ]
    scenario_name = str(draft.get("scenario_name") or result.request.scenario_name or "").strip()
    type_like_names = {SCENARIO_TYPE_LABELS[result.request.scenario_type], "سناریوی شعبه محوری"}
    if scenario_name and scenario_name not in type_like_names:
        chips.append(f'<span>نام سناریو: {html.escape(scenario_name)}</span>')
    chips.append(f'<span>{html.escape(persian_digits(changed_count))} شاخص تغییریافته</span>')
    return (
        '<section class="results-context-strip" data-results-context="true">'
        f'<span class="results-context-icon">{icon_svg("bank")}</span>'
        f'<div>{"".join(chips)}</div></section>'
    )


def _result_header_html(draft) -> str:
    persistence = dict(draft.get("persistence") or {})
    status = "ذخیره‌شده" if persistence.get("status") == "executed" else "ذخیره‌نشده" if not persistence.get("scenario_id") else "آماده بررسی"
    return (
        '<header class="results-workspace-header" data-results-header="true"><div>'
        '<h1>نتیجه اجرای سناریوی شعبه‌محور</h1>'
        '<p>اثر تغییرات سناریو بر امتیاز، رتبه و درجه شعبه را بررسی کنید.</p></div>'
        f'<span>{html.escape(status)}</span></header>'
    )


def _managerial_summary_html(comparison, changed_count: int) -> str:
    rank_tone = _rank_tone(int(comparison.rank_change))
    score_change = float(comparison.score_change)
    score_tone = _score_tone(score_change)
    grade_changed = comparison.baseline_grade != comparison.scenario_grade
    cards = (
        ("رتبه شعبه", "رتبه فعلی", format_persian_number(comparison.baseline_rank, 0), "رتبه سناریو",
         format_persian_number(comparison.scenario_rank, 0), _rank_movement_text(comparison.rank_change), rank_tone, _movement_icon(comparison.rank_change)),
        ("امتیاز کل", "امتیاز کل فعلی", format_persian_number(comparison.baseline_final_score, 1), "امتیاز کل سناریو",
         format_persian_number(comparison.scenario_final_score, 1), f"تغییر امتیاز کل {format_signed_persian_number(score_change, 1)}", score_tone, _movement_icon(score_change)),
        ("درجه شعبه", "درجه فعلی", format_grade(comparison.baseline_grade), "درجه سناریو",
         format_grade(comparison.scenario_grade), "درجه بدون تغییر" if not grade_changed else f"تغییر درجه به {format_grade(comparison.scenario_grade)}", "neutral" if not grade_changed else score_tone, "−" if not grade_changed else _movement_icon(score_change)),
        ("شاخص‌های مؤثر", "شاخص انتخاب‌شده", format_persian_number(len(comparison.indicator_comparisons), 0), "شاخص تغییریافته",
         format_persian_number(changed_count, 0), "بر پایه نتیجه رسمی شاخص‌ها", "neutral", "−"),
    )
    body = "".join(
        f'<article class="result-glance-card {tone}"><header><h3>{html.escape(title)}</h3>'
        f'<span class="result-trend-icon" aria-hidden="true">{html.escape(icon)}</span></header>'
        '<div class="result-glance-values">'
        f'<div><span>{html.escape(current_label)}</span><strong class="numeric-fa" dir="rtl">{html.escape(str(current))}</strong></div>'
        f'<div><span>{html.escape(scenario_label)}</span><strong class="numeric-fa scenario" dir="rtl">{html.escape(str(scenario))}</strong></div></div>'
        f'<p class="result-change-pill"><span class="result-trend-icon small" aria-hidden="true">{html.escape(icon)}</span>{html.escape(change)}</p></article>'
        for title, current_label, current, scenario_label, scenario, change, tone, icon in cards
    )
    return '<section class="result-glance"><header><h2>نتیجه در یک نگاه</h2></header><div>' + body + '</div></section>'


def _calculation_rows(comparison) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in comparison.indicator_comparisons:
        key = item["indicator_key"]
        rows.append({
            "indicator_key": key,
            "name": INDICATOR_REGISTRY[key].display_name,
            "weight": format_persian_percentage(WEIGHTS[key] * 100, 1),
            "current_raw": format_persian_number(item["baseline_raw_value"], 0),
            "scenario_raw": format_persian_number(item["scenario_raw_value"], 0),
            "raw_change": format_signed_persian_number(item["raw_value_change"], 0),
            "raw_change_pct": format_signed_persian_percentage(item["raw_value_change_pct"], 1),
            "baseline_rank": format_persian_number(item["baseline_indicator_rank"], 0),
            "scenario_rank": format_persian_number(item["scenario_indicator_rank"], 0),
            "rank_change": _rank_movement_text(item["indicator_rank_change"]),
            "baseline_weighted": format_persian_number(item["baseline_weighted_score"], 1),
            "scenario_weighted": format_persian_number(item["scenario_weighted_score"], 1),
            "weighted_effect": format_signed_persian_number(item["weighted_score_change"], 1),
            "changed": abs(float(item["raw_value_change"])) > 1e-9,
            "tone": _score_tone(float(item["weighted_score_change"])),
            "rank_tone": _rank_tone(int(item["indicator_rank_change"])),
            "details": (
                ("مقدار فعلی", format_persian_number(item["baseline_raw_value"], 0)),
                ("مقدار سناریو", format_persian_number(item["scenario_raw_value"], 0)),
                ("تغییر درصدی", format_signed_persian_percentage(item["raw_value_change_pct"], 1)),
                ("امتیاز رسمی فعلی", format_persian_number(item["baseline_score"], 1)),
                ("امتیاز رسمی سناریو", format_persian_number(item["scenario_score"], 1)),
                ("تغییر امتیاز رسمی", format_signed_persian_number(item["score_change"], 1)),
                ("وزن رسمی شاخص", format_persian_percentage(WEIGHTS[key] * 100, 1)),
                ("اثر بر امتیاز کل", format_signed_persian_number(item["weighted_score_change"], 1)),
            ),
        })
    return rows


def _branch_result_cards_html(title: str, items, names: dict[str, str]) -> str:
    cards = []
    for item in items:
        rank_tone = "success" if int(item.rank_change) > 0 else "danger" if int(item.rank_change) < 0 else "neutral"
        score_change = float(item.scenario_final_score) - float(item.baseline_final_score)
        score_tone = "success" if score_change > 0 else "danger" if score_change < 0 else "neutral"
        grade_changed = item.baseline_grade != item.scenario_grade
        rows = (
            ("target", "رتبه کل", f"رتبه پایه {format_persian_number(item.baseline_rank, 0)}", f"رتبه سناریو {format_persian_number(item.scenario_rank, 0)}", persian_digits(rank_change_presentation(int(item.rank_change))[0]), rank_tone),
            ("folder", "امتیاز کل", f"امتیاز پایه {format_persian_number(item.baseline_final_score, 1)}", f"امتیاز سناریو {format_persian_number(item.scenario_final_score, 1)}", f"{format_signed_persian_number(score_change, 1)} امتیاز", score_tone),
            ("bank", "درجه شعبه", f"درجه پایه {format_grade(item.baseline_grade)}", f"درجه سناریو {format_grade(item.scenario_grade)}", "تغییر درجه" if grade_changed else "بدون تغییر درجه", score_tone if grade_changed else "neutral"),
        )
        body = "".join(
            f'<div class="branch-result-row {tone}"><span class="branch-result-icon">{icon_svg(icon)}</span>'
            f'<section><h4>{html.escape(label)}</h4><div><b>{html.escape(current)}</b><i aria-hidden="true">←</i><b>{html.escape(scenario)}</b></div>'
            f'<em>{html.escape(change)}</em></section></div>'
            for icon, label, current, scenario, change, tone in rows
        )
        cards.append(
            '<article class="branch-result-card">'
            f'<header><strong>{icon_svg("bank")} {html.escape(names.get(str(item.branch_id), str(item.branch_id)))}</strong>'
            f'<span>کد {html.escape(persian_digits(item.branch_id))}</span></header>{body}</article>'
        )
    return f'<section class="branch-result-section"><h3>{html.escape(title)}</h3><div class="branch-result-grid">{"".join(cards)}</div></section>'


def _branch_section(title: str, items, data) -> None:
    names = data.assign(**{BRANCH_ID: data[BRANCH_ID].astype(str)}).set_index(BRANCH_ID)[BRANCH_NAME].to_dict()
    st.caption(f"تعداد کل: {persian_digits(f'{len(items):,}')}")
    if not items: render_empty_state("موردی در این بخش وجود ندارد."); return
    rows = [{"شعبه": names.get(item.branch_id, item.branch_id), "کد": persian_digits(item.branch_id), "رتبه پایه": format_persian_number(item.baseline_rank, 0),
             "رتبه سناریو": format_persian_number(item.scenario_rank, 0), "تغییر رتبه": persian_digits(item.rank_change), "امتیاز پایه": format_persian_number(item.baseline_final_score, 1),
             "امتیاز سناریو": format_persian_number(item.scenario_final_score, 1), "درجه پایه": format_grade(item.baseline_grade), "درجه سناریو": format_grade(item.scenario_grade)} for item in items]
    st.markdown(_branch_result_cards_html(title, items, names), unsafe_allow_html=True)
    with st.expander("نمایش جدولی شعب", expanded=False):
        st.dataframe(rows, width="stretch", height=360, hide_index=True)


def _calculation_detail_cards(detailed: list[dict[str, str]]) -> str:
    cards = []
    for row in detailed:
        absolute_text = str(row["تغییر مطلق"])
        tone = "danger" if absolute_text.startswith("−") or absolute_text.startswith("-") else "success" if absolute_text.startswith("+") else "neutral"
        cards.append(
            f'<article class="calculation-detail-card {tone}"><header><div><h3>{html.escape(row["شاخص"])}</h3>'
            f'<span>وضعیت: {"دارای تغییر" if tone != "neutral" else "بدون تغییر"}</span></div>'
            f'<b>وزن واقعی {html.escape(row["وزن واقعی شاخص"])}</b></header>'
            '<section><h4>داده ورودی</h4><div class="detail-pair">'
            f'<div><span>مقدار فعلی</span><strong>{html.escape(row["مقدار فعلی"])}</strong></div>'
            f'<div><span>مقدار سناریو</span><strong>{html.escape(row["مقدار سناریو"])}</strong></div></div></section>'
            '<section><h4>اثر تغییر</h4><div class="detail-pair">'
            f'<div><span>تغییر مطلق</span><strong>{html.escape(row["تغییر مطلق"])}</strong></div>'
            f'<div><span>تغییر درصدی</span><strong>{html.escape(row["تغییر درصدی"])}</strong></div></div></section>'
            '<section><h4>امتیاز شاخص</h4><div class="detail-triplet">'
            f'<div><span>امتیاز فعلی</span><strong>{html.escape(row["امتیاز نرمال‌شده فعلی"])}</strong></div>'
            f'<div><span>امتیاز سناریو</span><strong>{html.escape(row["امتیاز نرمال‌شده سناریو"])}</strong></div>'
            f'<div><span>تغییر امتیاز</span><strong>{html.escape(row["تغییر امتیاز نرمال‌شده"])}</strong></div></div></section>'
            '<section><h4>امتیاز موزون</h4><div class="detail-triplet">'
            f'<div><span>امتیاز موزون فعلی</span><strong>{html.escape(row["امتیاز موزون فعلی"])}</strong></div>'
            f'<div><span>امتیاز موزون سناریو</span><strong>{html.escape(row["امتیاز موزون سناریو"])}</strong></div>'
            f'<div><span>اثر بر امتیاز کل</span><strong>{html.escape(row["اثر بر امتیاز کل"])}</strong></div></div></section>'
            '<details><summary>روش محاسبه</summary><p>امتیاز موزون از امتیاز نرمال‌شده و وزن واقعی شاخص محاسبه و فقط برای نمایش قالب‌بندی شده است.</p></details>'
            '</article>'
        )
    return f'<div class="calculation-detail-grid">{ "".join(cards) }</div>'


def _empty_result_panel(message: str) -> None:
    st.markdown(
        '<section class="results-empty-state">'
        f'<span>{icon_svg("folder")}</span><p>{html.escape(message)}</p></section>',
        unsafe_allow_html=True,
    )


def _calculation_table_html(rows: list[dict[str, object]], comparison) -> str:
    headers = (
        "شاخص", "وزن", "مقدار فعلی", "مقدار سناریو", "تغییر", "رتبه فعلی شاخص",
        "رتبه سناریوی شاخص", "جابه‌جایی رتبه", "امتیاز موزون فعلی",
        "امتیاز موزون سناریو", "اثر بر امتیاز کل", "جزئیات",
    )
    head = "".join(f"<th>{html.escape(label)}</th>" for label in headers)
    body = []
    for index, row in enumerate(rows, 1):
        changed_badge = '<em>تغییریافته</em>' if row["changed"] else '<em class="neutral">بدون تغییر</em>'
        body.append(
            f'<tr class="calc-main-row {row["tone"]} {"changed" if row["changed"] else "unchanged"}">'
            f'<td class="indicator-cell"><strong>{html.escape(str(row["name"]))}</strong>{changed_badge}</td>'
            f'<td class="numeric-fa">{html.escape(str(row["weight"]))}</td>'
            f'<td class="numeric-fa">{html.escape(str(row["current_raw"]))}</td>'
            f'<td class="numeric-fa scenario">{html.escape(str(row["scenario_raw"]))}</td>'
            f'<td class="numeric-fa {row["tone"]}">{html.escape(str(row["raw_change"]))}</td>'
            f'<td class="numeric-fa">{html.escape(str(row["baseline_rank"]))}</td>'
            f'<td class="numeric-fa scenario">{html.escape(str(row["scenario_rank"]))}</td>'
            f'<td class="{row["rank_tone"]}"><b aria-hidden="true">{_movement_icon(1 if row["rank_tone"] == "success" else -1 if row["rank_tone"] == "danger" else 0)}</b>{html.escape(str(row["rank_change"]))}</td>'
            f'<td class="numeric-fa">{html.escape(str(row["baseline_weighted"]))}</td>'
            f'<td class="numeric-fa scenario">{html.escape(str(row["scenario_weighted"]))}</td>'
            f'<td class="numeric-fa {row["tone"]}">{html.escape(str(row["weighted_effect"]))}</td>'
            f'<td><details class="result-calc-details"><summary class="calc-detail-toggle" aria-label="نمایش جزئیات {html.escape(str(row["name"]))}">'
            '<span class="calc-detail-chevron" aria-hidden="true">⌄</span></summary>'
            '<div class="calc-detail-panel">'
            + "".join(f'<span><small>{html.escape(label)}</small><b class="numeric-fa">{html.escape(str(value))}</b></span>' for label, value in row["details"])
            + '</div></details></td></tr>'
        )
    total_effect = float(comparison.scenario_final_score) - float(comparison.baseline_final_score)
    body.append(
        '<tr class="calc-summary-row"><td>جمع / نتیجه کل</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'
        f'<td class="numeric-fa">{html.escape(format_persian_number(comparison.baseline_final_score, 1))}</td>'
        f'<td class="numeric-fa scenario">{html.escape(format_persian_number(comparison.scenario_final_score, 1))}</td>'
        f'<td class="numeric-fa {_score_tone(total_effect)}">{html.escape(format_signed_persian_number(total_effect, 1))}</td><td></td></tr>'
    )
    return (
        '<section class="results-tab-panel calculation-panel" data-calculation-details="true">'
        '<header><h2>جزئیات کامل محاسبات</h2>'
        '<p>اثر هر شاخص بر امتیاز و رتبه شعبه، با مقایسه وضعیت فعلی و سناریو</p></header>'
        '<div class="calculation-table-wrap"><table class="calculation-table">'
        f'<thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div></section>'
    )


def _changed_indicators_html(rows: list[dict[str, object]]) -> str:
    changed = [row for row in rows if row["changed"]]
    if not changed:
        return ""
    increased = sum(1 for row in changed if str(row["raw_change"]).startswith("+"))
    decreased = sum(1 for row in changed if str(row["raw_change"]).startswith("−") or str(row["raw_change"]).startswith("-"))
    chips = (
        f'<span>افزایش: <b>{persian_digits(increased)}</b></span>'
        f'<span>کاهش: <b>{persian_digits(decreased)}</b></span>'
        f'<span>کل: <b>{persian_digits(len(changed))}</b></span>'
    )
    cards = "".join(
        f'<article class="changed-indicator-card {row["tone"]}"><header><h3>{html.escape(str(row["name"]))}</h3>'
        f'<span>{html.escape(str(row["rank_change"]))}</span></header>'
        '<div>'
        f'<span>مقدار فعلی <b class="numeric-fa">{html.escape(str(row["current_raw"]))}</b></span>'
        f'<span>مقدار سناریو <b class="numeric-fa scenario">{html.escape(str(row["scenario_raw"]))}</b></span>'
        f'<span>تغییر <b class="numeric-fa">{html.escape(str(row["raw_change"]))}</b></span>'
        f'<span>تغییر درصدی <b class="numeric-fa">{html.escape(str(row["raw_change_pct"]))}</b></span>'
        f'<span>امتیاز موزون فعلی <b class="numeric-fa">{html.escape(str(row["baseline_weighted"]))}</b></span>'
        f'<span>امتیاز موزون سناریو <b class="numeric-fa scenario">{html.escape(str(row["scenario_weighted"]))}</b></span>'
        f'<span>اثر بر امتیاز کل <b class="numeric-fa">{html.escape(str(row["weighted_effect"]))}</b></span>'
        '</div></article>'
        for row in changed
    )
    return f'<section class="changed-indicators-panel"><div class="results-chip-row">{chips}</div><div>{cards}</div></section>'


def _branch_rows(items, names: dict[str, str], focus_branch_id: str) -> list[dict[str, object]]:
    rows = []
    for item in items:
        rank_change = int(item.rank_change)
        rows.append({
            "branch_id": str(item.branch_id),
            "name": names.get(str(item.branch_id), str(item.branch_id)),
            "code": persian_digits(item.branch_id),
            "baseline_rank": format_persian_number(item.baseline_rank, 0),
            "scenario_rank": format_persian_number(item.scenario_rank, 0),
            "rank_change": _rank_movement_text(rank_change),
            "rank_change_numeric": rank_change,
            "baseline_score": format_persian_number(item.baseline_final_score, 1),
            "scenario_score": format_persian_number(item.scenario_final_score, 1),
            "score_change": format_signed_persian_number(item.score_change, 1),
            "tone": _rank_tone(rank_change),
            "status": "شعبه سناریو" if str(item.branch_id) == focus_branch_id else ("صعود رتبه" if rank_change > 0 else "نزول رتبه" if rank_change < 0 else "بدون تغییر"),
            "focus": str(item.branch_id) == focus_branch_id,
        })
    return sorted(rows, key=lambda row: abs(int(row["rank_change_numeric"])), reverse=True)


RANK_FILTER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("all", "همه"),
    ("up", "صعود رتبه"),
    ("down", "نزول رتبه"),
    ("unchanged", "بدون تغییر"),
)


def _rank_status_key(current_rank: object, scenario_rank: object) -> str | None:
    current = pd.to_numeric(current_rank, errors="coerce")
    scenario = pd.to_numeric(scenario_rank, errors="coerce")
    if pd.isna(current) or pd.isna(scenario):
        return None
    if float(scenario) < float(current):
        return "up"
    if float(scenario) > float(current):
        return "down"
    return "unchanged"


def _complete_rank_rows(result, names: dict[str, str], focus_branch_id: str) -> list[dict[str, object]]:
    source = result.comparison_results.branch_comparison
    rows = []
    seen: set[str] = set()
    for record in source.to_dict("records"):
        branch_id = str(record[BRANCH_ID])
        if branch_id in seen:
            continue
        seen.add(branch_id)
        status_key = _rank_status_key(record.get("baseline_rank"), record.get("scenario_rank"))
        if status_key is None:
            continue
        rank_change = int(float(record["baseline_rank"]) - float(record["scenario_rank"]))
        rows.append({
            "branch_id": branch_id,
            "name": names.get(branch_id, branch_id),
            "code": persian_digits(branch_id),
            "baseline_rank": format_persian_number(record["baseline_rank"], 0),
            "scenario_rank": format_persian_number(record["scenario_rank"], 0),
            "baseline_rank_numeric": int(float(record["baseline_rank"])),
            "scenario_rank_numeric": int(float(record["scenario_rank"])),
            "rank_change": _rank_movement_text(rank_change),
            "rank_change_numeric": rank_change,
            "baseline_score": format_persian_number(record["baseline_score"], 1),
            "scenario_score": format_persian_number(record["scenario_score"], 1),
            "score_change": format_signed_persian_number(record["score_change"], 1),
            "tone": _rank_tone(rank_change),
            "status_key": status_key,
            "status": dict(RANK_FILTER_OPTIONS)[status_key],
            "focus": branch_id == focus_branch_id,
        })
    return sorted(rows, key=lambda row: (0 if row["focus"] else 1, -abs(int(row["rank_change_numeric"])), int(row["baseline_rank_numeric"])))


def _rank_counter(rows: list[dict[str, object]], key: str) -> int:
    return sum(1 for row in rows if row.get("status_key") == key)


def _filter_rank_rows(rows: list[dict[str, object]], filter_key: str, query: str) -> list[dict[str, object]]:
    normalized_query = str(query or "").strip()
    query_fa = persian_digits(normalized_query)
    filtered = [
        row for row in rows
        if filter_key == "all" or row.get("status_key") == filter_key
    ]
    if not normalized_query:
        return filtered
    return [
        row for row in filtered
        if normalized_query in str(row["name"])
        or normalized_query in str(row["branch_id"])
        or query_fa in str(row["code"])
    ]


def _rank_empty_message(filter_key: str, query: str) -> str:
    if str(query or "").strip():
        return "شعبه‌ای مطابق عبارت جست‌وجو یافت نشد."
    return {
        "up": "شعبه‌ای با صعود رتبه یافت نشد.",
        "down": "شعبه‌ای با نزول رتبه یافت نشد.",
        "unchanged": "شعبه‌ای با رتبه بدون تغییر یافت نشد.",
    }.get(filter_key, "موردی برای نمایش وجود ندارد.")


def _branch_impact_table_html(rows: list[dict[str, object]]) -> str:
    body = "".join(
        f'<tr class="{row["tone"]} {"focus" if row["focus"] else ""}"><td><strong>{html.escape(str(row["name"]))}</strong></td>'
        f'<td class="numeric-fa">{html.escape(str(row["code"]))}</td><td class="numeric-fa">{html.escape(str(row["baseline_rank"]))}</td>'
        f'<td class="numeric-fa scenario">{html.escape(str(row["scenario_rank"]))}</td><td><b aria-hidden="true">{_movement_icon(row["rank_change_numeric"])}</b>{html.escape(str(row["rank_change"]))}</td>'
        f'<td class="numeric-fa">{html.escape(str(row["baseline_score"]))}</td><td class="numeric-fa scenario">{html.escape(str(row["scenario_score"]))}</td>'
        f'<td class="numeric-fa">{html.escape(str(row["score_change"]))}</td><td>{html.escape(str(row["status"]))}</td></tr>'
        for row in rows
    )
    return (
        '<div class="branch-impact-table-wrap"><table class="branch-impact-table"><thead><tr>'
        '<th>شعبه</th><th>کد شعبه</th><th>رتبه فعلی</th><th>رتبه سناریو</th><th>جابه‌جایی رتبه</th>'
        '<th>امتیاز فعلی</th><th>امتیاز سناریو</th><th>تغییر امتیاز</th><th>وضعیت</th></tr></thead>'
        f'<tbody>{body}</tbody></table></div>'
    )


def _data_change_rows(items, names: dict[str, str], focus_branch_id: str) -> list[dict[str, object]]:
    rows = []
    for branch in items:
        branch_id = str(branch.branch_id)
        for item in branch.indicator_comparisons:
            if abs(float(item.get("raw_value_change", 0.0))) <= 1e-9:
                continue
            rows.append({
                "branch_id": branch_id,
                "name": names.get(branch_id, branch_id),
                "code": persian_digits(branch_id),
                "indicator": INDICATOR_REGISTRY[item["indicator_key"]].display_name,
                "current_raw": format_persian_number(item["baseline_raw_value"], 0),
                "scenario_raw": format_persian_number(item["scenario_raw_value"], 0),
                "absolute": format_signed_persian_number(item["raw_value_change"], 0),
                "percent": format_signed_persian_percentage(item["raw_value_change_pct"], 1),
                "tone": _score_tone(float(item["raw_value_change"])),
                "focus": branch_id == focus_branch_id,
            })
    return rows


def _data_change_table_html(rows: list[dict[str, object]]) -> str:
    body = "".join(
        f'<tr class="{row["tone"]} {"focus" if row["focus"] else ""}"><td><strong>{html.escape(str(row["name"]))}</strong></td>'
        f'<td class="numeric-fa">{html.escape(str(row["code"]))}</td><td>{html.escape(str(row["indicator"]))}</td>'
        f'<td class="numeric-fa">{html.escape(str(row["current_raw"]))}</td><td class="numeric-fa scenario">{html.escape(str(row["scenario_raw"]))}</td>'
        f'<td class="numeric-fa">{html.escape(str(row["absolute"]))}</td><td class="numeric-fa">{html.escape(str(row["percent"]))}</td>'
        '<td>تغییر مستقیم سناریو</td></tr>'
        for row in rows
    )
    return (
        '<div class="branch-impact-table-wrap"><table class="branch-impact-table data-change-table"><thead><tr>'
        '<th>شعبه</th><th>کد شعبه</th><th>شاخص</th><th>مقدار فعلی</th><th>مقدار سناریو</th>'
        '<th>تفاوت مطلق</th><th>تفاوت درصدی</th><th>نوع تغییر</th></tr></thead>'
        f'<tbody>{body}</tbody></table></div>'
    )


def _focus_result_page(draft, data, result, comparison) -> None:
    names = data.assign(**{BRANCH_ID: data[BRANCH_ID].astype(str)}).set_index(BRANCH_ID)[BRANCH_NAME].astype(str).to_dict()
    calc_rows = _calculation_rows(comparison)
    changed_rows = [row for row in calc_rows if row["changed"]]
    rank_rows_all = _complete_rank_rows(result, names, str(result.request.focus_branch_id))
    modified_rows = _data_change_rows(result.modified_branches, names, str(result.request.focus_branch_id))
    st.markdown(_result_header_html(draft), unsafe_allow_html=True)
    st.markdown(_result_context_html(draft, result, comparison, names), unsafe_allow_html=True)
    st.markdown(_managerial_summary_html(comparison, len(changed_rows)), unsafe_allow_html=True)
    labels = (
        f"جزئیات محاسبات {persian_digits(len(calc_rows))}",
        f"شاخص‌های تغییریافته {persian_digits(len(changed_rows))}",
        f"شعب متأثر در رتبه‌بندی {persian_digits(_rank_counter(rank_rows_all, 'up') + _rank_counter(rank_rows_all, 'down'))}",
        f"شعب دارای تغییر در داده‌ها {persian_digits(len(modified_rows))}",
    )
    st.markdown('<div class="results-tabs-anchor" data-default-results-tab="calculation-details"></div>', unsafe_allow_html=True)
    tab_calc, tab_changed, tab_rank, tab_data = st.tabs(labels)
    with tab_calc:
        st.markdown(_calculation_table_html(calc_rows, comparison), unsafe_allow_html=True)
        preview = rank_rows_all[:3]
        if preview:
            st.markdown('<section class="rank-preview"><h3>بیشترین جابه‌جایی در رتبه‌بندی</h3>' + _branch_impact_table_html(preview) + '</section>', unsafe_allow_html=True)
    with tab_changed:
        st.markdown('<section class="results-tab-panel"><header><h2>شاخص‌های تغییریافته</h2><p>شاخص‌هایی که مقدار سناریوی آن‌ها با وضعیت فعلی متفاوت است.</p></header></section>', unsafe_allow_html=True)
        changed_html = _changed_indicators_html(calc_rows)
        if changed_html:
            st.markdown(changed_html, unsafe_allow_html=True)
        else:
            _empty_result_panel("در این سناریو مقدار هیچ شاخصی تغییر نکرده است.")
    with tab_rank:
        st.markdown('<section class="results-tab-panel"><header><h2>شعب متأثر در رتبه‌بندی</h2><p>شعبی که در نتیجه اجرای این سناریو، جایگاه رتبه‌بندی آن‌ها تغییر کرده است.</p></header></section>', unsafe_allow_html=True)
        asc = _rank_counter(rank_rows_all, "up")
        desc = _rank_counter(rank_rows_all, "down")
        unchanged = _rank_counter(rank_rows_all, "unchanged")
        max_move = max((abs(int(row["rank_change_numeric"])) for row in rank_rows_all), default=0)
        st.markdown(
            '<div class="branch-impact-summary">'
            f'<span>کل شعب بررسی‌شده <b>{persian_digits(len(rank_rows_all))}</b></span>'
            f'<span>کل شعب متأثر <b>{persian_digits(asc + desc)}</b></span>'
            f'<span>شعب صعودکرده <b>{persian_digits(asc)}</b></span>'
            f'<span>شعب نزول‌کرده <b>{persian_digits(desc)}</b></span>'
            f'<span>بدون تغییر <b>{persian_digits(unchanged)}</b></span>'
            f'<span>بیشترین جابه‌جایی <b>{persian_digits(max_move)}</b></span></div>',
            unsafe_allow_html=True,
        )
        filters = st.columns([2, 1])
        query = filters[0].text_input("جست‌وجوی شعبه یا کد", key="result_rank_branch_search")
        direction_filter = filters[1].selectbox(
            "فیلتر رتبه",
            [key for key, _ in RANK_FILTER_OPTIONS],
            format_func=dict(RANK_FILTER_OPTIONS).get,
            key="result_rank_direction_filter",
        )
        filtered = _filter_rank_rows(rank_rows_all, direction_filter, query)
        if filtered:
            st.markdown(_branch_impact_table_html(filtered), unsafe_allow_html=True)
        else:
            _empty_result_panel(_rank_empty_message(direction_filter, query))
    with tab_data:
        st.markdown('<section class="results-tab-panel"><header><h2>شعب دارای تغییر در داده‌ها</h2><p>شعبی که مقادیر ورودی آن‌ها مستقیماً در سناریو تغییر کرده است.</p></header></section>', unsafe_allow_html=True)
        if modified_rows:
            st.markdown(_data_change_table_html(modified_rows), unsafe_allow_html=True)
        else:
            _empty_result_panel("در این سناریو داده‌ای برای سایر شعب تغییر نکرده است.")
    _result_actions_bar(draft)


def _result_page(draft, data) -> None:
    result = draft["execution_result"]
    names = data.assign(**{BRANCH_ID: data[BRANCH_ID].astype(str)}).set_index(BRANCH_ID)[BRANCH_NAME].to_dict()
    st.info(_scenario_context(draft, names))
    options = result_branch_options(result)
    current = str(draft.get("selected_result_branch_id") or result.request.focus_branch_id)
    if current not in options: current = options[0]
    selected = st.selectbox("مشاهده نتایج شعبه", options, index=options.index(current),
                            format_func=lambda item: _branch_label(item, names), key="official_result_branch")
    draft["selected_result_branch_id"] = selected
    comparison = select_official_branch_result(result, selected)
    if result.request.scenario_type is ScenarioType.FOCUS_BRANCH_ONLY:
        _focus_result_page(draft, data, result, comparison)
        return
    change_text, _ = rank_change_presentation(comparison.rank_change)
    cards = st.columns(4)
    cards[0].metric("رتبه", comparison.scenario_rank, change_text)
    cards[1].metric("امتیاز نهایی", format_score(comparison.scenario_final_score), f"{comparison.score_change:+.1f}")
    cards[2].metric("درجه", format_grade(comparison.scenario_grade))
    cards[3].metric("تعداد شعب دارای تغییر واقعی", len(result.modified_branches))
    st.subheader("مقایسه شاخص‌های شعبه انتخاب‌شده")
    if comparison.indicator_comparisons:
        rows = [{"شاخص": INDICATOR_REGISTRY[item["indicator_key"]].display_name,
                 "مقدار پایه": format_raw_value(item["baseline_raw_value"]), "مقدار سناریو": format_raw_value(item["scenario_raw_value"]),
                 "تغییر مقدار خام": format_raw_value(item["raw_value_change"]), "امتیاز نرمال‌شده فعلی": format_score(item["baseline_score"]),
                 "امتیاز نرمال‌شده سناریو": format_score(item["scenario_score"]), "اثر بر امتیاز کل": format_score(item["weighted_score_change"])}
                for item in comparison.indicator_comparisons]
        st.dataframe(rows, width="stretch", height=360, hide_index=True)
    else:
        st.info("جزئیات شاخص‌های این شعبه در قرارداد نتیجه فعلی موجود نیست؛ مقایسه رتبه، امتیاز و درجه نمایش داده شد.")
    _branch_section("شعب دارای تغییر در شاخص‌ها", result.modified_branches, data)
    _branch_section("شعب دارای تغییر در رتبه، امتیاز یا درجه", result.rank_affected_branches, data)
    _render_result_actions(draft)


def _persisted_result_page(draft, data) -> None:
    results = list(draft.get("persisted_result_summaries") or [])
    if not results:
        render_empty_state("خلاصه نتیجه ذخیره‌شده‌ای برای این سناریو موجود نیست.")
        return
    names = data.assign(**{BRANCH_ID: data[BRANCH_ID].astype(str)}).set_index(BRANCH_ID)[BRANCH_NAME].to_dict()
    focus = str(draft.get("focus_branch_id") or "")
    ids = list(dict.fromkeys([focus, *(str(item.branch_id) for item in results)]))
    ids = [item for item in ids if item and any(str(row.branch_id) == item for row in results)]
    selected = st.selectbox("مشاهده نتایج شعبه", ids, format_func=lambda item: _branch_label(item, names), key="persisted_result_branch")
    item = next(row for row in results if str(row.branch_id) == selected)
    cards = st.columns(3)
    cards[0].metric("رتبه", item.scenario_rank, rank_change_presentation(item.rank_change)[0])
    cards[1].metric("امتیاز نهایی", format_score(item.scenario_score), f"{item.score_change:+.1f}")
    cards[2].metric("درجه", format_grade(item.scenario_grade))
    st.info("جزئیات شاخص‌های هر شعبه در خلاصه نتیجه ذخیره‌شده موجود نیست؛ مقایسه رسمی رتبه، امتیاز و درجه نمایش داده شد.")
    if st.button("بازگشت و ویرایش"):
        draft["show_result"] = False; draft["persisted_result_summaries"] = []; st.rerun()


def _target_indicator_rows(path_result, *, include_effect: bool = False) -> str:
    rows = []
    for item in path_result.solution.indicator_proposals:
        exact_current = persian_digits(format_compact_number(item.baseline_raw_value))
        exact_proposed = persian_digits(format_compact_number(item.proposed_raw_value))
        effect = (item.scenario_weighted_contribution or 0) - (item.baseline_weighted_contribution or 0)
        effect_html = (
            f'<span><small>اثر امتیاز</small><b>{html.escape(format_signed_persian_number(effect, 1))}</b></span>'
            if include_effect else ""
        )
        rows.append(
            '<article class="target-rank-indicator-row">'
            f'<div><i>{icon_svg("target")}</i><strong>{html.escape(INDICATOR_REGISTRY[item.indicator_id].display_name)}</strong></div>'
            f'<span title="{html.escape(exact_current)}"><small>فعلی</small><b>{html.escape(persian_digits(format_managerial_number(item.baseline_raw_value)))}</b></span>'
            '<em aria-hidden="true">←</em>'
            f'<span title="{html.escape(exact_proposed)}"><small>پیشنهادی</small><b>{html.escape(persian_digits(format_managerial_number(item.proposed_raw_value)))}</b></span>'
            f'<span><small>درصد تغییر</small><b>{html.escape(format_persian_percentage(item.percent_change, 1))}</b></span>'
            f'<span><small>وزن رسمی</small><b>{html.escape(format_persian_percentage(WEIGHTS[item.indicator_id] * 100, 0))}</b></span>'
            f'{effect_html}</article>'
        )
    return "".join(rows) or f'<p>{html.escape(path_result.solution.message)}</p>'


def _target_indicator_analysis_panel(path_result) -> str:
    comparisons = {
        item["indicator_key"]: item
        for item in (path_result.solution.comparison.indicator_comparisons if path_result.solution.comparison else ())
    }
    cards = []
    for item in path_result.solution.indicator_proposals:
        comparison = comparisons.get(item.indicator_id, {})
        rank_change = int(comparison.get("indicator_rank_change", 0) or 0)
        rank_text, rank_tone = rank_change_presentation(rank_change)
        effect = (item.scenario_weighted_contribution or 0) - (item.baseline_weighted_contribution or 0)
        tone = "success" if effect > 0 else "danger" if effect < 0 else "neutral"
        cards.append(
            f'<article class="target-rank-indicator-card {tone}">'
            f'<header class="target-rank-indicator-card-header"><span class="target-rank-card-icon">{icon_svg("target")}</span>'
            f'<div><h4 class="target-rank-indicator-name">{html.escape(INDICATOR_REGISTRY[item.indicator_id].display_name)}</h4>'
            f'<p>{html.escape(format_persian_percentage(WEIGHTS[item.indicator_id] * 100, 0))} وزن رسمی</p></div>'
            f'<em class="target-rank-rank-badge {rank_tone}">{html.escape(persian_digits(rank_text))}</em></header>'
            '<div class="target-rank-indicator-value-row">'
            f'<b title="{html.escape(persian_digits(format_compact_number(item.baseline_raw_value)))}"><small>مقدار فعلی</small>{html.escape(persian_digits(format_managerial_number(item.baseline_raw_value)))}</b>'
            '<em aria-hidden="true">←</em>'
            f'<b title="{html.escape(persian_digits(format_compact_number(item.proposed_raw_value)))}" class="scenario"><small>مقدار پیشنهادی</small>{html.escape(persian_digits(format_managerial_number(item.proposed_raw_value)))}</b>'
            '</div><div class="target-rank-indicator-metrics">'
            f'<b><small>تغییر مطلق</small>{html.escape(format_signed_persian_number(item.absolute_change, 0))}</b>'
            f'<b><small>درصد تغییر</small>{html.escape(format_persian_percentage(item.percent_change, 1))}</b>'
            f'<b><small>وزن رسمی</small>{html.escape(format_persian_percentage(WEIGHTS[item.indicator_id] * 100, 0))}</b>'
            f'<b><small>امتیاز موزون فعلی</small>{html.escape(format_persian_number(item.baseline_weighted_contribution, 1))}</b>'
            f'<b class="scenario"><small>امتیاز موزون سناریو</small>{html.escape(format_persian_number(item.scenario_weighted_contribution, 1))}</b>'
            f'<b class="{tone}"><small>اثر بر امتیاز کل</small>{html.escape(format_signed_persian_number(effect, 1))}</b>'
            '</div><footer class="target-rank-indicator-footer">'
            f'<b><small>رتبه فعلی شاخص</small>{html.escape(persian_digits(comparison.get("baseline_indicator_rank", "—")))}</b>'
            f'<b><small>رتبه سناریوی شاخص</small>{html.escape(persian_digits(comparison.get("scenario_indicator_rank", "—")))}</b>'
            f'<b class="{rank_tone}"><small>جابه‌جایی رتبه شاخص</small>{html.escape(persian_digits(rank_text))}</b>'
            '</footer></article>'
        )
    return (
        f'<section class="target-rank-indicator-analysis" data-target-path="{html.escape(path_result.path.path_id)}">'
        f'<header><h3>{html.escape(path_result.path.display_name)}</h3><p>{html.escape(path_result.path.explanation)}</p></header>'
        f'<div>{"".join(cards)}</div></section>'
    )


def _target_path_card(path_result, *, phase: str = "final", compact: bool = False) -> str:
    solution = path_result.solution
    final = phase == "final"
    status_class = "success" if final and solution.target_reached else "danger" if final else "proposal"
    status_text = "هدف محقق شد" if final and solution.target_reached else "هدف محقق نشد" if final else "آماده اجرا"
    metrics = [
        ("تعداد شاخص‌ها", len(path_result.path.selected_indicator_ids)),
        ("درصد تغییر مشترک پیشنهادی", format_percentage(solution.required_common_growth_percent)),
        ("رتبه هدف", solution.target_rank),
    ]
    if final:
        metrics.extend([
            ("رتبه فعلی", solution.baseline_rank or "—"),
            ("رتبه نهایی", solution.achieved_rank or "—"),
            ("بهبود رتبه", solution.rank_change if solution.rank_change is not None else "—"),
            ("امتیاز فعلی", format_score(solution.baseline_score) if solution.baseline_score is not None else "—"),
            ("امتیاز نهایی", format_score(solution.achieved_score) if solution.achieved_score is not None else "—"),
            ("تغییر امتیاز", format_signed_persian_number((solution.achieved_score or 0) - (solution.baseline_score or 0), 1) if solution.achieved_score is not None and solution.baseline_score is not None else "—"),
            ("درجه فعلی", format_grade(solution.comparison.baseline_grade) if solution.comparison else "—"),
            ("درجه نهایی", format_grade(solution.comparison.scenario_grade) if solution.comparison else "—"),
        ])
    metric_html = "".join(
        f'<span class="target-rank-path-kpi"><small>{html.escape(label)}</small><b>{html.escape(persian_digits(value))}</b></span>'
        for label, value in metrics
    )
    accent = "navy" if path_result.path.path_id == "all_indicators_balanced" else "purple"
    names = "، ".join(INDICATOR_REGISTRY[key].display_name for key in path_result.path.selected_indicator_ids)
    included_chips = "".join(
        f"<span>{html.escape(INDICATOR_REGISTRY[key].display_name)}</span>"
        for key in path_result.path.selected_indicator_ids
    )
    phase_class = ""
    return (
        f'<article class="target-rank-path-card target-rank-path-panel {phase_class} {status_class} {accent}" data-target-path="{html.escape(path_result.path.path_id)}">'
        f'<header><span class="target-rank-card-icon">{icon_svg("target")}</span><div><h3>{html.escape(path_result.path.display_name)}</h3>'
        f'<p>{html.escape(path_result.path.explanation)}</p></div><em>{status_text}</em><b>{html.escape(persian_digits(len(path_result.path.selected_indicator_ids)))} شاخص</b></header>'
        '<div class="target-rank-path-content">'
        f'<div class="target-rank-path-metrics target-rank-path-kpi-grid">{metric_html}</div>'
        f'<div class="target-rank-included" title="{html.escape(names)}"><small>شاخص‌های مسیر</small><div class="target-rank-path-chips">{included_chips}</div></div>'
        f'<div class="target-rank-proposal-list target-rank-path-indicator-list">{_target_indicator_rows(path_result, include_effect=final)}</div>'
        '</div>'
        '</article>'
    )


def _execute_target_comparison(draft, data) -> None:
    try:
        request = build_target_comparison_request(draft)
        with st.spinner("در حال محاسبه و اجرای دو مسیر با مدل رسمی..."):
            comparison = ScenarioExecutionService().solve_target_rank_comparison(request, data)
    except (ValueError, KeyError) as exc:
        st.error(service_error_message(str(exc))); return
    except Exception:
        LOGGER.exception("Unexpected target-rank comparison failure")
        st.error("محاسبه رتبه هدف با خطای پیش‌بینی‌نشده روبه‌رو شد. لطفاً دوباره تلاش کنید."); return
    draft["target_comparison_result"] = comparison
    draft["target_execution_completed"] = True


def _target_step_one(draft, data, outputs, user) -> None:
    _select_focus(draft, data, outputs, user)
    if not draft.get("focus_branch_id"):
        return
    _indicator_picker(draft, data, outputs)
    if st.button("اجرای سناریو و مقایسه دو مسیر", type="primary", width="stretch", key="target_rank_execute_paths", disabled=bool(draft.get("target_execution_in_progress"))):
        if not str(draft.get("scenario_name") or "").strip():
            st.error("نام سناریو را وارد کنید.")
            return
        if not draft.get("focus_branch_id"):
            st.error("شعبه هدف را انتخاب کنید.")
            return
        if "target_rank" not in dict(draft.get("target_rank_request") or {}):
            st.error("رتبه هدف باید بهتر از رتبه فعلی شعبه باشد.")
            return
        if not draft.get("selected_indicator_ids"):
            st.error("برای تشکیل مسیر منتخب کاربر، حداقل یک شاخص را انتخاب کنید.")
            return
        draft["target_execution_in_progress"] = True
        try:
            _execute_target_comparison(draft, data)
        finally:
            draft["target_execution_in_progress"] = False
        if draft.get("target_comparison_result") is None:
            return
        draft["target_solution"] = draft["target_comparison_result"].user_selected_indicators.solution
        draft["target_execution_timestamp"] = datetime.now().isoformat(timespec="seconds")
        draft["current_step"] = 2
        st.rerun()


def _target_final_results(draft, data) -> None:
    comparison = draft.get("target_comparison_result")
    if comparison is None or not draft.get("target_execution_completed"):
        st.warning("ابتدا دو مسیر رتبه هدف را محاسبه و اجرا کنید.")
        return
    names = data.assign(**{BRANCH_ID: data[BRANCH_ID].astype(str)}).set_index(BRANCH_ID)[BRANCH_NAME].astype(str).to_dict()
    branch_id = str(comparison.focus_branch_id)
    branch_name = names.get(branch_id, branch_id)
    timestamp = draft.get("target_execution_timestamp") or datetime.now().isoformat(timespec="seconds")
    status = "موفق" if comparison.target_reached else "نیازمند بازبینی"
    st.markdown(
        '<section class="target-rank-result-page target-rank-hero target-rank-result-hero"><header><div><h1>نتیجه سناریوی رتبه هدف</h1>'
        f'<p>{html.escape(str(draft.get("scenario_name") or "سناریوی رتبه هدف"))}</p></div>'
        f'<em>{html.escape(status)}</em></header><div class="target-rank-hero-grid target-rank-result-meta-grid">'
        f'<span class="target-rank-result-meta-item"><small>شعبه</small><b>{html.escape(branch_name)}</b></span>'
        f'<span class="target-rank-result-meta-item"><small>کد شعبه</small><b>{html.escape(persian_digits(branch_id))}</b></span>'
        f'<span class="target-rank-result-meta-item"><small>رتبه فعلی</small><b>{html.escape(persian_digits(comparison.balanced_all_indicators.solution.baseline_rank or "—"))}</b></span>'
        f'<span class="target-rank-result-meta-item"><small>رتبه هدف</small><b>{html.escape(persian_digits(comparison.target_rank))}</b></span>'
        f'<span class="target-rank-result-meta-item"><small>زمان اجرا</small><b class="target-rank-result-timestamp" dir="ltr">{html.escape(timestamp)}</b></span>'
        '</div></section>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<section class="target-rank-result-page target-rank-result-grid">'
        f'{_target_path_card(comparison.balanced_all_indicators, phase="final")}'
        f'{_target_path_card(comparison.user_selected_indicators, phase="final")}'
        '</section>',
        unsafe_allow_html=True,
    )
    tab_indicators, tab_audit = st.tabs(["تحلیل شاخص‌ها", "جزئیات و ممیزی"])
    with tab_indicators:
        st.markdown(
            '<section class="target-rank-result-page target-rank-analysis-grid">'
            f'{_target_indicator_analysis_panel(comparison.balanced_all_indicators)}'
            f'{_target_indicator_analysis_panel(comparison.user_selected_indicators)}'
            '</section>',
            unsafe_allow_html=True,
        )
    with tab_audit:
        st.markdown(
            '<section class="target-rank-audit-panel"><h3>جزئیات درخواست و ممیزی</h3>'
            f'<p>رتبه هدف: {html.escape(persian_digits(comparison.target_rank))}</p>'
            f'<p>تعداد کل تکرار حل‌گر: {html.escape(persian_digits(comparison.iterations))}</p></section>',
            unsafe_allow_html=True,
        )
        for path_result in (comparison.balanced_all_indicators, comparison.user_selected_indicators):
            if path_result.solution.scenario_outputs is not None and path_result.solution.baseline_outputs is not None:
                frame = target_solution_comparison(path_result.solution)
                with st.expander(f"جدول کامل شعب متأثر - {path_result.path.display_name}"):
                    display_frame = frame.rename(columns={
                        BRANCH_ID: "کد شعبه", BRANCH_NAME: "نام شعبه",
                        "baseline_rank": "رتبه فعلی", "scenario_rank": "رتبه سناریو",
                        "rank_change": "تغییر رتبه", "baseline_score": "امتیاز فعلی",
                        "scenario_score": "امتیاز سناریو", "score_change": "تغییر امتیاز",
                        "baseline_grade": "درجه فعلی", "scenario_grade": "درجه سناریو",
                    }).copy()
                    for column in display_frame.select_dtypes(include=["float", "int"]).columns:
                        display_frame[column] = display_frame[column].map(lambda value: persian_digits(format_compact_number(value)))
                    st.dataframe(display_frame, width="stretch", hide_index=True)
                    st.download_button(
                        "دریافت CSV",
                        display_frame.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"target_rank_{path_result.path.path_id}.csv",
                        mime="text/csv",
                        key=f"target_rank_csv_{path_result.path.path_id}",
                    )
    actions = st.columns([1.4, 1.1, 5])
    if actions[0].button("ذخیره سناریو", key="save_target_comparison_execution", type="primary", disabled=bool(draft.get("target_save_in_progress"))):
        draft["target_save_in_progress"] = True
        _save_execution(draft)
        draft["target_save_in_progress"] = False
    if actions[1].button("بازگشت و ویرایش", key="target_result_back_to_edit_secondary"):
        draft["current_step"] = 1
        st.rerun()


def _navigation(draft) -> None:
    st.markdown('<div class="builder-action-row" data-builder-actions="true"></div>', unsafe_allow_html=True)
    columns = st.columns([1.35, 1.35, 5.55])
    last_step = 4
    next_disabled = draft["current_step"] >= last_step
    if columns[0].button("مرحله بعد", disabled=next_disabled, type="primary", width="stretch"):
        draft["current_step"] += 1; st.rerun()
    if columns[1].button("مرحله قبل", disabled=draft["current_step"] <= 1, width="stretch"):
        draft["current_step"] -= 1; st.rerun()


def main() -> None:
    initialize_session_state(); activate_requested_scenario()
    draft = st.session_state[SENSITIVITY_DRAFT_KEY]
    apply_global_styles(active_scenario=draft.get("scenario_type"))
    if draft.get("scenario_type") is None:
        st.switch_page("app.py")
        return
    try: data, outputs = load_baseline()
    except (FileNotFoundError, ValueError, OSError): st.error("اطلاعات مبنا بارگذاری نشد."); return
    try: user = load_current_user(ROOT / "config/local_user.json")
    except (FileNotFoundError, ValueError, OSError): st.error("اطلاعات کاربر در دسترس نیست."); return
    mode = draft["scenario_type"]
    if mode is ScenarioType.MULTI_BRANCH:
        render_multi_branch_workspace(
            data, outputs, user, multi_branch_workspace_service()
        )
        return
    _scenario_page_header(mode)
    if mode is ScenarioType.FOCUS_BRANCH_ONLY:
        if draft.get("entry_source") == "saved":
            st.info("پیش‌نویس ذخیره‌شده باز شده است؛ شعبه و تغییرات ذخیره‌شده برای ادامه کار بازیابی شده‌اند.")
    for warning in st.session_state.pop("sensitivity_restore_warnings", []):
        st.warning(warning)
    _scenario_name_panel(draft, data)
    if draft.get("show_result") and draft.get("persisted_result_summaries"):
        _persisted_result_page(draft, data); return
    if draft.get("show_result") and draft.get("execution_result") is not None:
        _result_page(draft, data); return
    if mode is ScenarioType.TARGET_RANK and draft.get("current_step") == 2:
        if not draft.get("target_execution_completed"):
            draft["current_step"] = 1
            st.rerun()
        _target_final_results(draft, data)
        return
    _wizard_header(draft)
    step = draft["current_step"]
    if mode is ScenarioType.TARGET_RANK:
        if step == 1: _target_step_one(draft, data, outputs, user)
        else: _target_final_results(draft, data)
    elif step == 1: _select_focus(draft, data, outputs, user)
    elif not draft.get("focus_branch_id"): st.warning("ابتدا شعبه محوری را انتخاب کنید.")
    elif mode is ScenarioType.FOCUS_BRANCH_ONLY:
        if step == 2: _indicator_picker(draft, data, outputs)
        elif step == 3: _focus_changes(draft, data)
        else:
            _review(draft, data)
            if st.button("اجرای سناریو", type="primary", width="stretch"): _execute(draft, data)
    elif mode is ScenarioType.MULTI_BRANCH:
        if step == 2: _add_bulk_rule(draft, data)
        elif step == 3: _add_override(draft, data)
        else:
            _review(draft, data)
            if st.button("اجرای سناریو", type="primary", width="stretch"): _execute(draft, data)
    if mode is not ScenarioType.TARGET_RANK:
        _navigation(draft)


if __name__ == "__main__":
    main()
