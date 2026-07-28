"""Three-mode Persian RTL sensitivity workspace."""

from __future__ import annotations

import html
from pathlib import Path
import logging

import pandas as pd
import streamlit as st

from domain.scenario_contracts import ScenarioExecutionResult, ScenarioType, TargetRankStatus
from engine.indicator_registry import INDICATOR_REGISTRY, PROFIT_LOSS_KEY
from engine.ranking_engine import BRANCH_ID, BRANCH_NAME, INDICATOR_TYPES, REGION, WEIGHTS
from engine.scenario_rule_engine import RuleOperation
from services.focus_branch import FocusBranchSource, resolve_focus_branch
from services.scenario_execution_service import ScenarioExecutionService, ScenarioRequestValidationError
from services.selection_scope import SelectionResolver, SelectionScope
from services.user_context import load_current_user
from services.factory import create_local_scenario_service
from services.scenario_workspace_service import ScenarioWorkspaceService
from persistence.contracts import ConcurrencyError, ScenarioPersistenceError
from ui import initialize_session_state
from ui.components import render_empty_state, render_page_header
from ui.data_access import load_dashboard_data
from ui.formatters import (
    format_compact_number, format_editable_number, format_grade, format_percentage,
    format_persian_number, format_persian_percentage, format_rank, format_raw_input_value, format_raw_value,
    format_score, format_signed_persian_number, parse_formatted_number, parse_raw_input_value, persian_digits,
)
from ui.sensitivity_adapters import (
    action_priority, build_focus_request, build_multi_request, build_target_request,
    count_proposal_presentation, preview_raw_operation, rank_change_presentation,
    focus_result_presentation,
    result_branch_options, select_official_branch_result, service_error_message,
    target_solution_comparison, unique_indicator_ids,
)
from ui.sensitivity_labels import (
    INDICATOR_TYPE_LABELS, MODE_COLORS, OPERATION_LABELS, SCENARIO_TYPE_LABELS,
    SCOPE_LABELS, TARGET_STATUS_LABELS,
)
from ui.sensitivity_components import (
    render_indicator_cards, render_process_timeline, render_summary_cards,
    render_value_comparison, render_wizard_steps,
)
from ui.sensitivity_state import (
    SESSION_HISTORY_KEY, SENSITIVITY_DRAFT_KEY,
    delete_bulk_rule, delete_manual_override,
    return_to_edit, set_focus_branch, set_multi_branch_selection,
    set_selected_indicators, switch_scenario_mode,
)
from ui.styles import apply_global_styles
from ui.navigation import activate_requested_scenario, branch_select_label, icon_svg

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
    try:
        workspace_service().save_execution(draft)
    except Exception as exc:
        _persistence_error(exc)
    else:
        st.success("نتیجه رسمی سناریو ذخیره شد")


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
    st.markdown(
        '<div class="selected-branch-banner" data-selected-branch-banner="true">'
        f'<span>شعبه انتخاب‌شده: {html.escape(names.get(str(branch_id), "شعبه"))} — کد '
        f'<bdi>{html.escape(persian_digits(branch_id))}</bdi></span></div>',
        unsafe_allow_html=True,
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
    return ("انتخاب شعبه و رتبه هدف", "انتخاب شاخص‌های قابل تغییر", "تنظیم محدوده بررسی", "محاسبه و پیشنهاد")


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
                                     value=int(draft["target_rank_request"].get("target_rank", max(1, baseline_rank - 1))), step=1)
            draft["target_rank_request"]["target_rank"] = int(target)
            if target >= baseline_rank:
                st.info("شعبه هم‌اکنون رتبه درخواستی را دارد یا از آن بهتر است؛ تغییری لازم نیست.")


def _indicator_picker(draft, data, outputs) -> None:
    branch_id = draft["focus_branch_id"]
    raw, _ = _focus_row(data, outputs, branch_id)
    selected = list(draft.get("selected_indicator_ids", []))
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


def _focus_changes(draft, data) -> None:
    raw = data.loc[data[BRANCH_ID].astype(str).eq(str(draft["focus_branch_id"]))].iloc[0]
    for indicator_id in draft["selected_indicator_ids"]:
        definition = INDICATOR_REGISTRY[indicator_id]
        saved = draft["focus_changes"].get(indicator_id, {})
        with st.container(border=True):
            st.markdown(
                '<div class="scenario-edit-card" data-scenario-edit-card="true">'
                f'<header><h3>{html.escape(definition.display_name)}</h3>'
                f'<span>مقدار پایه: <b class="numeric-fa">{html.escape(format_persian_number(raw[indicator_id], 0))}</b></span></header></div>',
                unsafe_allow_html=True,
            )
            control = st.container()
            st.markdown('<div class="scenario-edit-controls">', unsafe_allow_html=True)
            columns = control.columns([1.25, 1, 1.35])
            operation = columns[0].selectbox("نوع تغییر", OPERATIONS,
                index=OPERATIONS.index(RuleOperation(saved.get("operation", RuleOperation.PERCENT_CHANGE.value))),
                format_func=OPERATION_LABELS.get, key=f"focus_op_{indicator_id}")
            saved_value = float(saved.get("value", 0.0))
            if operation is not RuleOperation.SET_VALUE:
                direction = columns[1].radio(
                    "جهت تغییر", (1, -1), index=1 if saved_value < 0 else 0,
                    format_func=lambda item: "افزایش (+)" if item == 1 else "کاهش (−)",
                    horizontal=True, key=f"focus_direction_{indicator_id}_{operation.value}",
                )
                input_label = "مقدار تغییر (٪)" if operation is RuleOperation.PERCENT_CHANGE else "مقدار قابل افزودن یا کسر"
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
                    "مقدار نهایی جایگزین", value=saved_value,
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


def _focus_result_page(draft, data, result, comparison) -> None:
    summaries, indicator_cards = focus_result_presentation(comparison)
    render_summary_cards(summaries, len(indicator_cards))
    st.subheader("اثر سناریو بر شاخص‌های تغییریافته")
    if indicator_cards: render_indicator_cards(indicator_cards)
    else: render_empty_state("هیچ شاخصی در این سناریو تغییر نکرده است.")
    with st.expander("جزئیات کامل محاسبات", expanded=False):
        detailed = [{
            "شاخص": INDICATOR_REGISTRY[item["indicator_key"]].display_name,
            "مقدار فعلی": format_persian_number(item["baseline_raw_value"], 0),
            "مقدار سناریو": format_persian_number(item["scenario_raw_value"], 0),
            "تغییر مطلق": format_signed_persian_number(item["raw_value_change"], 0),
            "تغییر درصدی": format_persian_percentage(item["raw_value_change_pct"], 1),
            "امتیاز نرمال‌شده فعلی": format_persian_number(item["baseline_score"], 1),
            "امتیاز نرمال‌شده سناریو": format_persian_number(item["scenario_score"], 1),
            "تغییر امتیاز نرمال‌شده": format_signed_persian_number(float(item["scenario_score"]) - float(item["baseline_score"]), 1),
            "فرمول امتیاز موزون": "امتیاز نرمال‌شده × وزن واقعی شاخص",
            "وزن واقعی شاخص": format_persian_percentage(WEIGHTS[item["indicator_key"]] * 100, 1),
            "امتیاز موزون فعلی": format_persian_number(float(item["baseline_score"]) * WEIGHTS[item["indicator_key"]], 1),
            "امتیاز موزون سناریو": format_persian_number(float(item["scenario_score"]) * WEIGHTS[item["indicator_key"]], 1),
            "اثر بر امتیاز کل": format_signed_persian_number((float(item["scenario_score"]) - float(item["baseline_score"])) * WEIGHTS[item["indicator_key"]], 1),
        } for item in comparison.indicator_comparisons]
        st.markdown(_calculation_detail_cards(detailed), unsafe_allow_html=True)
        with st.expander("نمایش داده خام جدولی", expanded=False):
            st.dataframe(detailed, width="stretch", height=360, hide_index=True)
        if any(item["indicator_key"] == "profit_loss" for item in comparison.indicator_comparisons):
            st.info("امتیاز نرمال‌شده سود و زیان براساس دامنه مقادیر مدل و قواعد تبدیل مقادیر منفی محاسبه می‌شود؛ بنابراین برای تفسیر مدیریتی، مقدار واقعی، رتبه شاخص و امتیاز موزون مبنای اصلی نمایش قرار گرفته‌اند.")
        _branch_section("شعب دارای تغییر در داده‌ها", result.modified_branches, data)
        _branch_section("شعب متأثر در رتبه‌بندی", result.rank_affected_branches, data)
    _render_result_actions(draft)


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


def _target_settings(draft) -> None:
    settings = draft["target_rank_request"]
    settings["max_growth_percent"] = st.number_input("حداکثر رشد قابل بررسی", min_value=0.01, value=float(settings.get("max_growth_percent", 100.0)), step=5.0)
    with st.expander("تنظیمات پیشرفته"):
        settings["minimum_growth_percent"] = st.number_input("حداقل رشد قابل بررسی", min_value=0.0, value=float(settings.get("minimum_growth_percent", 0.0)))
        settings["tolerance_percent"] = st.number_input("حد پذیرش محاسبه", min_value=0.0001, value=float(settings.get("tolerance_percent", 0.01)), format="%.4f")
        settings["search_precision_percent"] = st.number_input("دقت پیشنهاد", min_value=0.0001, value=float(settings.get("search_precision_percent", 0.01)), format="%.4f")
        settings["max_iterations"] = st.number_input("حداکثر مراحل بررسی", min_value=1, value=int(settings.get("max_iterations", 40)), step=1)


def _solve_target(draft, data) -> None:
    try:
        request = build_target_request(draft)
        with st.spinner("در حال محاسبه تغییرات متوازن موردنیاز..."):
            solution = ScenarioExecutionService().solve_target_rank(request, data)
    except (ValueError, KeyError) as exc:
        st.error(service_error_message(str(exc))); return
    except Exception:
        LOGGER.exception("Unexpected target-rank execution failure")
        st.error("محاسبه رتبه هدف با خطای پیش‌بینی‌نشده روبه‌رو شد. لطفاً دوباره تلاش کنید."); return
    draft["target_solution"] = solution
    st.session_state[SESSION_HISTORY_KEY].append({"نام سناریو": draft.get("scenario_name") or SCENARIO_TYPE_LABELS[ScenarioType.TARGET_RANK], "نوع": SCENARIO_TYPE_LABELS[ScenarioType.TARGET_RANK], "شعبه محوری": request.focus_branch_id})
    st.rerun()


def _target_result(draft, data) -> None:
    solution = draft["target_solution"]
    status = TARGET_STATUS_LABELS[solution.status]
    (st.success if solution.target_reached else st.warning)(status)
    cards = st.columns(4)
    cards[0].metric("رتبه پایه", solution.baseline_rank or "—")
    cards[1].metric("رتبه هدف", solution.target_rank)
    cards[2].metric("رتبه حاصل‌شده", solution.achieved_rank or "—")
    cards[3].metric("رشد مشترک موردنیاز", format_percentage(solution.required_common_growth_percent))
    if solution.status is TargetRankStatus.MAX_ITERATIONS_REACHED:
        st.info("ممکن است یک پیشنهاد موفق پیدا شده باشد، اما کمترین رشد موردنیاز در محدوده تنظیمات با قطعیت تعیین نشده است.")
        st.write(f"تعیین قطعی حداقل رشد: {'بله' if solution.minimum_growth_established else 'خیر'}")
    if solution.status is TargetRankStatus.TARGET_NOT_REACHABLE:
        st.info(f"حداکثر رشد بررسی‌شده: {format_percentage(solution.required_common_growth_percent)}. سقف رشد یا شاخص‌های منتخب را بازبینی کنید.")
    if solution.indicator_proposals:
        rows = []
        for proposal in solution.indicator_proposals:
            shown = count_proposal_presentation(proposal)
            rows.append({"شاخص": INDICATOR_REGISTRY[proposal.indicator_id].display_name, "مقدار پایه": proposal.baseline_raw_value,
                         "پیشنهاد قابل اجرا": shown["applicable_value"], "تغییر مطلق": proposal.absolute_change, "درصد تغییر": proposal.percent_change})
            if shown["show_ceiling_note"]: st.caption(f"{INDICATOR_REGISTRY[proposal.indicator_id].display_name}: پیشنهاد شمارشی با گرد کردن رو به بالا به عدد صحیح و اجرای دوباره مدل رسمی تأیید شده است.")
            if proposal.indicator_id == PROFIT_LOSS_KEY and proposal.baseline_raw_value == 0:
                st.info("مقدار صفر سود و زیان به دلیل نداشتن مبنای غیرصفر، با تغییر درصدی تغییر نکرد.")
        st.caption(f"تعداد کل پیشنهادها: {len(rows):,}")
        st.dataframe(rows, width="stretch", height=320, hide_index=True)
        priorities, tied = action_priority(solution.indicator_proposals)
        if priorities:
            st.subheader("اولویت اقدامات")
            st.caption("اولویت بر اساس اثر واقعی امتیاز موزون هر شاخص بر امتیاز کل این سناریو")
            st.dataframe([{"شاخص": INDICATOR_REGISTRY[row["indicator_id"]].display_name, "اثر بر امتیاز کل": row["weighted_contribution_delta"]} for row in priorities], width="stretch", height=280, hide_index=True)
            if tied: st.info("در این سناریو تفاوت معناداری میان اولویت شاخص‌ها دیده نمی‌شود.")
        else:
            st.info("در این سناریو اثر مثبت و قابل تفکیکی از امتیاز موزون شاخص‌ها بر امتیاز کل دیده نمی‌شود.")
    if solution.scenario_outputs is not None and solution.baseline_outputs is not None:
        if st.button("ذخیره نتیجه رسمی", key="save_target_execution"):
            _save_execution(draft)
        if st.button("اعمال پیشنهاد و مشاهده نتایج کامل", type="primary"):
            draft["show_result"] = True; st.rerun()
        if draft.get("show_result"):
            _target_full_result(solution)


def _target_full_result(solution) -> None:
    st.subheader("نتیجه کامل اجرای رسمی")
    frame = target_solution_comparison(solution).copy()
    focus = frame.loc[frame[BRANCH_ID].astype(str).eq(str(solution.focus_branch_id))].iloc[0]
    movement, _ = rank_change_presentation(int(focus["rank_change"]))
    cards = st.columns(4)
    cards[0].metric("رتبه", int(focus["scenario_rank"]), movement)
    cards[1].metric("امتیاز نهایی", format_score(focus["scenario_score"]), f"{float(focus['score_change']):+.1f}")
    cards[2].metric("درجه", format_grade(focus["scenario_grade"]))
    cards[3].metric("تعداد شعب دارای تغییر واقعی", 1 if solution.indicator_proposals else 0)
    st.subheader("مقایسه شاخص‌های شعبه محوری")
    st.dataframe([{"شاخص": INDICATOR_REGISTRY[item.indicator_id].display_name, "مقدار پایه": item.baseline_raw_value,
                   "مقدار سناریو": item.proposed_raw_value, "تغییر مقدار خام": item.absolute_change,
                   "امتیاز نرمال‌شده فعلی": item.baseline_normalized_score, "امتیاز نرمال‌شده سناریو": item.scenario_normalized_score,
                   "اثر بر امتیاز کل": (item.scenario_weighted_contribution or 0) - (item.baseline_weighted_contribution or 0)}
                  for item in solution.indicator_proposals], width="stretch", hide_index=True)
    modified = frame.loc[frame[BRANCH_ID].astype(str).eq(str(solution.focus_branch_id))] if solution.indicator_proposals else frame.iloc[0:0]
    affected = frame.loc[frame["rank_change"].ne(0) | frame["score_change"].ne(0) | frame["grade_changed"]]
    def display(source):
        return pd.DataFrame({"نام شعبه": source[BRANCH_NAME], "کد شعبه": source[BRANCH_ID], "رتبه پایه": source["baseline_rank"],
            "رتبه سناریو": source["scenario_rank"], "تغییر رتبه": source["rank_change"], "امتیاز پایه": source["baseline_score"],
            "امتیاز سناریو": source["scenario_score"], "درجه پایه": source["baseline_grade"].map(format_grade),
            "درجه سناریو": source["scenario_grade"].map(format_grade)})
    st.subheader("شعب دارای تغییر در شاخص‌ها")
    st.caption(f"تعداد کل: {len(modified):,}")
    st.dataframe(display(modified), width="stretch", height=320, hide_index=True)
    st.subheader("شعب دارای تغییر در رتبه، امتیاز یا درجه")
    st.caption(f"تعداد کل: {len(affected):,}")
    st.dataframe(display(affected), width="stretch", height=360, hide_index=True)


def _navigation(draft) -> None:
    st.markdown('<div class="builder-action-row" data-builder-actions="true"></div>', unsafe_allow_html=True)
    columns = st.columns([1.35, 1.35, 5.55])
    if columns[0].button("مرحله بعد", disabled=draft["current_step"] >= 4, type="primary", width="stretch"):
        draft["current_step"] += 1; st.rerun()
    if columns[1].button("مرحله قبل", disabled=draft["current_step"] <= 1, width="stretch"):
        draft["current_step"] -= 1; st.rerun()


def main() -> None:
    initialize_session_state(); activate_requested_scenario()
    draft = st.session_state[SENSITIVITY_DRAFT_KEY]
    apply_global_styles(active_scenario=draft.get("scenario_type"))
    if draft.get("scenario_type") is None:
        render_page_header("فضای تحلیل حساسیت", "برای شروع، نوع سناریو را انتخاب کنید.")
        for column, mode in zip(st.columns(3), ScenarioType):
            if column.button(SCENARIO_TYPE_LABELS[mode], key=f"choose_{mode.value}", width="stretch"):
                switch_scenario_mode(st.session_state, mode); st.rerun()
        return
    try: data, outputs = load_baseline()
    except (FileNotFoundError, ValueError, OSError): st.error("اطلاعات مبنا بارگذاری نشد."); return
    try: user = load_current_user(ROOT / "config/local_user.json")
    except (FileNotFoundError, ValueError, OSError): st.error("اطلاعات کاربر در دسترس نیست."); return
    mode = draft["scenario_type"]
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
    if mode is ScenarioType.TARGET_RANK and draft.get("target_solution") is not None:
        _target_result(draft, data)
        if st.button("بازگشت و ویرایش تحلیل"): return_to_edit(draft); st.rerun()
        return
    _wizard_header(draft)
    step = draft["current_step"]
    if step == 1: _select_focus(draft, data, outputs, user)
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
    else:
        if step == 2: _indicator_picker(draft, data, outputs)
        elif step == 3: _target_settings(draft)
        else:
            _review_target = draft["target_rank_request"]
            st.write(f"رتبه هدف: {_review_target.get('target_rank', '—')}")
            st.write(f"تعداد شاخص‌های قابل تغییر: {len(draft['selected_indicator_ids'])}")
            st.write(f"حداکثر رشد قابل بررسی: {format_percentage(_review_target.get('max_growth_percent'))}")
            if st.button("محاسبه و پیشنهاد", type="primary", width="stretch"): _solve_target(draft, data)
    _navigation(draft)


main()
