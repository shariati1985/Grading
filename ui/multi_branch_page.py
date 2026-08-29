"""Dedicated five-stage multi-branch scenario workspace."""

from __future__ import annotations

from datetime import datetime
import html
from types import SimpleNamespace
import uuid

import pandas as pd
import streamlit as st

from domain.multi_branch_contracts import (
    ActorContext,
    ActorScope,
    BranchException,
    MultiBranchScenarioV1,
    PercentageDirection,
    PercentageRule,
    PopulationDefinition,
    PrimaryBranchOverride,
)
from engine.comparison_engine import compare_model_outputs
from engine.indicator_registry import INDICATOR_REGISTRY
from engine.ranking_engine import BRANCH_ID, BRANCH_NAME, run_ranking_model
from services.multi_branch_rule_resolver import (
    MultiBranchRuleResolver,
    MultiBranchRuleValidationError,
)
from services.primary_branch_policy import resolve_primary_branch
from services.multi_branch_workspace_service import MultiBranchWorkspaceService
from persistence.contracts import ConcurrencyError, ScenarioPersistenceError
from services.user_context import CurrentUser
from ui.formatters import format_persian_number, parse_formatted_number, parse_raw_input_value, persian_digits
from ui.multi_branch_state import (
    MULTI_BRANCH_STAGE_LABELS,
    MULTI_BRANCH_STAGE_ORDER,
    MultiBranchStage,
    consume_scroll_to_top,
    current_multi_branch_stage,
    initialize_multi_branch_state,
    invalidate_multi_branch_result,
    move_to_multi_branch_stage,
)
from ui.navigation import branch_select_label, icon_svg
from ui.multi_branch_results import render_multi_branch_results


def _branch_maps(data: pd.DataFrame) -> tuple[list[str], dict[str, str]]:
    normalized = data.assign(**{BRANCH_ID: data[BRANCH_ID].astype(str)})
    return (
        normalized[BRANCH_ID].tolist(),
        normalized.set_index(BRANCH_ID)[BRANCH_NAME].astype(str).to_dict(),
    )


def _stage_header(stage: MultiBranchStage, description: str) -> None:
    st.markdown(
        '<section class="multi-branch-stage-header">'
        f'<span>{icon_svg("buildings")}</span><div><h2>{html.escape(MULTI_BRANCH_STAGE_LABELS[stage])}</h2>'
        f'<p>{html.escape(description)}</p></div></section>',
        unsafe_allow_html=True,
    )


def _workflow(stage: MultiBranchStage) -> None:
    active_index = MULTI_BRANCH_STAGE_ORDER.index(stage)
    items = []
    for index, item in enumerate(MULTI_BRANCH_STAGE_ORDER):
        tone = " active" if item is stage else " completed" if index < active_index else ""
        items.append(
            f'<li class="{tone.strip()}"><b>{persian_digits(index + 1)}</b>'
            f'<span>{html.escape(MULTI_BRANCH_STAGE_LABELS[item])}</span></li>'
        )
    st.markdown(
        '<nav class="multi-branch-workflow" aria-label="مراحل سناریوی چندشعبه‌ای"><ol>'
        + "".join(items)
        + "</ol></nav>",
        unsafe_allow_html=True,
    )


def _actor_context(user: CurrentUser) -> ActorContext:
    assigned_branch = user.branch_id or user.branch_code
    return ActorContext(
        actor_id=user.user_id,
        actor_scope=ActorScope.BRANCH if assigned_branch else ActorScope.HEAD_OFFICE,
        assigned_branch_code=str(assigned_branch) if assigned_branch else None,
        can_select_primary_branch=True,
    )


def _scroll_to_top_once(workspace: dict) -> None:
    if not consume_scroll_to_top(workspace):
        return
    st.markdown(
        """
        <script>
        const main = window.parent.document.querySelector('[data-testid="stMain"]')
          || window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
        if (main) { main.scrollTo({top: 0, behavior: 'instant'}); }
        window.parent.scrollTo({top: 0, behavior: 'instant'});
        </script>
        """,
        unsafe_allow_html=True,
    )


def _parse_percentage_input(value: object) -> float:
    percentage = parse_formatted_number(value)
    if percentage <= 0:
        raise ValueError("درصد تغییر باید بزرگ‌تر از صفر باشد.")
    return float(percentage)


def _direction_label(direction: object) -> str:
    return "افزایش" if str(direction) == "increase" else "کاهش"


def _direction_sign(direction: object) -> int:
    return 1 if str(direction) == "increase" else -1


def _format_entered_percentage(value: object, direction: object) -> str:
    number = parse_formatted_number(value)
    rendered = format_persian_number(number, 2).rstrip("۰").rstrip("٫")
    return f"{rendered}٪ {_direction_label(direction)}"


def _primary_rule_summary(
    indicator_key: str,
    item: dict,
    baseline_value: float,
) -> dict[str, object]:
    mode = str(item["input_mode"])
    entered = float(item["input_value"])
    scenario_value = float(item["resolved_raw_value"])
    change_amount = scenario_value - float(baseline_value)
    if mode == "percent":
        direction = "increase" if entered >= 0 else "decrease"
        entered_text = _format_entered_percentage(abs(entered), direction)
        method = "تغییر درصدی"
    elif mode == "absolute":
        direction = "increase" if change_amount >= 0 else "decrease"
        entered_text = format_persian_number(entered, 0)
        method = "تغییر مطلق"
    else:
        direction = "increase" if change_amount >= 0 else "decrease"
        entered_text = format_persian_number(entered, 0)
        method = "مقدار نهایی"
    return {
        "indicator_key": indicator_key,
        "indicator": INDICATOR_REGISTRY[indicator_key].display_name,
        "method": method,
        "direction": _direction_label(direction),
        "entered": entered_text,
        "baseline": format_persian_number(baseline_value, 0),
        "change_amount": format_persian_number(change_amount, 0),
        "scenario_value": format_persian_number(scenario_value, 0),
    }


def _primary_rule_rows(overrides: dict[str, dict], baseline_row: pd.Series) -> pd.DataFrame:
    return pd.DataFrame([
        _primary_rule_summary(indicator, item, float(baseline_row[indicator]))
        for indicator, item in overrides.items()
    ])


def _ltr_value(value: object) -> str:
    rendered = "—" if value is None else str(value)
    return f'<strong dir="ltr">{html.escape(rendered)}</strong>'


def _review_fact(label: str, value: object) -> str:
    return f'<span><small>{html.escape(label)}</small>{_ltr_value(value)}</span>'


def _delete_button(label: str, key: str) -> bool:
    return st.button(label, key=key, width="stretch")


def _exception_used_indicators_for_branch(
    exceptions: dict[str, list[dict]], branch_code: object | None
) -> set[str]:
    if branch_code is None:
        return set()
    return {
        str(row.get("indicator_key"))
        for row in exceptions.get(str(branch_code), [])
        if row.get("indicator_key") is not None
    }


def get_available_exception_indicator_keys(
    all_indicator_keys: list[str] | tuple[str, ...],
    exceptions: dict[str, list[dict]],
    selected_branch_code: object | None,
) -> list[str]:
    used_for_branch = _exception_used_indicators_for_branch(exceptions, selected_branch_code)
    return [key for key in all_indicator_keys if key not in used_for_branch]


def _exception_indicator_options(
    exceptions: dict[str, list[dict]], branch_code: object | None
) -> list[str | None]:
    available = get_available_exception_indicator_keys(list(INDICATOR_REGISTRY), exceptions, branch_code)
    return [None, *available] if available else [None]


def _has_exception_rule(
    exceptions: dict[str, list[dict]], branch_code: object, indicator_key: object
) -> bool:
    branch = str(branch_code)
    indicator = str(indicator_key)
    return indicator in _exception_used_indicators_for_branch(exceptions, branch)


def _render_review_rule_card(rule: dict, branch_count: int) -> str:
    indicator = INDICATOR_REGISTRY[rule["indicator_key"]].display_name
    direction = _direction_label(rule["direction"])
    return (
        '<article class="multi-review-rule-card general">'
        f'<header><h3>{html.escape(indicator)}</h3><span>قاعده عمومی</span></header>'
        '<div class="multi-review-rule-body">'
        f'{_review_fact("دامنه", f"تمام {format_persian_number(branch_count, 0)} شعبه جامعه (کل شعب)")}'
        f'{_review_fact("جهت", direction)}'
        f'{_review_fact("درصد واردشده", _format_entered_percentage(rule["percentage"], rule["direction"]))}'
        '</div></article>'
    )


def _render_exception_card(branch_code: str, rule: dict, names: dict[str, str], general_keys: set[str]) -> str:
    indicator = INDICATOR_REGISTRY[rule["indicator_key"]].display_name
    status = "جایگزین قاعده عمومی" if rule["indicator_key"] in general_keys else "قاعده اختصاصی مستقل"
    return (
        '<article class="multi-review-rule-card exception">'
        f'<header><h3>{html.escape(names.get(str(branch_code), "—"))}</h3><span>{html.escape(status)}</span></header>'
        '<div class="multi-review-rule-body">'
        f'{_review_fact("کد شعبه", persian_digits(branch_code))}'
        f'{_review_fact("شاخص", indicator)}'
        f'{_review_fact("جهت", _direction_label(rule["direction"]))}'
        f'{_review_fact("درصد واردشده", _format_entered_percentage(rule["percentage"], rule["direction"]))}'
        '</div></article>'
    )


def _render_primary_rule_card(row: dict) -> str:
    cells = "".join(
        _review_fact(label, row.get(key))
        for label, key in (
            ("ورودی کاربر", "entered"),
            ("مقدار مبنا", "baseline"),
            ("مقدار تغییر", "change_amount"),
            ("مقدار نهایی", "scenario_value"),
        )
    )
    return (
        '<article class="multi-review-rule-card primary">'
        f'<header><h3>{html.escape(str(row.get("indicator") or "—"))}</h3><span>مقدار اختصاصی شعبه اصلی</span></header>'
        f'<p>{html.escape(str(row.get("method") or "—"))}</p><div class="multi-review-rule-body">{cells}</div></article>'
    )


def _review_section_html(title: str, body: str, css_class: str) -> str:
    return (
        f'<section class="multi-review-section {html.escape(css_class)}">'
        f'<h3>{html.escape(title)}</h3><div class="multi-review-card-grid">{body}</div></section>'
    )


def _general_rule_review_rows(workspace: dict) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "شاخص": INDICATOR_REGISTRY[rule["indicator_key"]].display_name,
            "جهت": _direction_label(rule["direction"]),
            "درصد واردشده": _format_entered_percentage(rule["percentage"], rule["direction"]),
            "دامنه اعمال": "تمام شعب جامعه (کل شعب)",
            "اولویت/منبع": "قاعده عمومی",
        }
        for rule in workspace["general_rules"]
    ])


def _exception_rule_review_rows(workspace: dict, names: dict[str, str]) -> pd.DataFrame:
    general_keys = {rule["indicator_key"] for rule in workspace["general_rules"]}
    rows = []
    for branch_code, rules in workspace["branch_exceptions"].items():
        for rule in rules:
            rows.append({
                "نام شعبه": names.get(str(branch_code), "—"),
                "کد شعبه": persian_digits(branch_code),
                "شاخص": INDICATOR_REGISTRY[rule["indicator_key"]].display_name,
                "جهت": _direction_label(rule["direction"]),
                "درصد واردشده": _format_entered_percentage(rule["percentage"], rule["direction"]),
                "وضعیت تقدم": "جایگزین قاعده عمومی" if rule["indicator_key"] in general_keys else "قاعده اختصاصی مستقل",
            })
    return pd.DataFrame(rows)


def _details(workspace: dict, data: pd.DataFrame, actor: ActorContext) -> None:
    _stage_header(
        MultiBranchStage.SCENARIO_DETAILS,
        "نام سناریو و شعبه اصلی را مشخص کنید. جامعه محاسبه، تمام شعب معتبر دوره مبنا است.",
    )
    ids, names = _branch_maps(data)
    with st.container(border=True):
        columns = st.columns([1.4, 1, 0.7])
        workspace["scenario_name"] = columns[0].text_input(
            "نام سناریو", value=str(workspace.get("scenario_name") or ""), key="multi_branch_name"
        )
        if not actor.can_select_primary_branch:
            assigned = resolve_primary_branch(actor, None)
            if assigned not in ids:
                st.error("شعبه تخصیص‌یافته کاربر در جامعه (کل شعب) رتبه‌بندی وجود ندارد.")
                workspace["primary_branch_code"] = None
            else:
                workspace["primary_branch_code"] = assigned
                columns[1].text_input(
                    "شعبه اصلی",
                    value=branch_select_label(assigned, names),
                    disabled=True,
                    key="multi_branch_assigned_primary",
                )
        else:
            current = workspace.get("primary_branch_code")
            index = ids.index(str(current)) + 1 if current is not None and str(current) in ids else 0
            selected = columns[1].selectbox(
                "شعبه اصلی",
                [None, *ids],
                index=index,
                format_func=lambda item: "انتخاب شعبه اصلی" if item is None else branch_select_label(item, names),
                key="multi_branch_primary",
            )
            workspace["primary_branch_code"] = resolve_primary_branch(
                actor, str(selected) if selected is not None else None
            )
        columns[2].metric("جامعه محاسبه", f"{format_persian_number(len(data), 0)} شعبه")
    st.info("انتخاب شعبه اصلی فقط برای نمایش نتیجه محوری و ثبت تغییرات صریح مرحله چهارم است؛ هیچ شعبه‌ای از جامعه رتبه‌بندی حذف نمی‌شود.")


def _rule_editor(workspace: dict) -> None:
    _stage_header(
        MultiBranchStage.GENERAL_RULES,
        "برای یک یا چند شاخص، تا هر ۸ شاخص، درصد عمومی مستقل تعریف کنید.",
    )
    rules = workspace["general_rules"]
    occupied = {row["indicator_key"] for row in rules}
    available = [key for key in INDICATOR_REGISTRY if key not in occupied]
    if available:
        st.markdown('<div class="multi-compact-form multi-general-rule-form">', unsafe_allow_html=True)
        with st.form("multi_general_rule_form"):
            columns = st.columns([1.7, 1.05, 0.95, 1.0])
            indicator = columns[0].selectbox(
                "شاخص",
                [None, *available],
                index=0,
                format_func=lambda key: "انتخاب شاخص" if key is None else INDICATOR_REGISTRY[key].display_name,
                key="multi_general_indicator",
            )
            direction = columns[1].radio(
                "جهت تغییر", ("increase", "decrease"),
                format_func=lambda value: "افزایش" if value == "increase" else "کاهش",
                horizontal=True,
                key="multi_general_direction",
            )
            percentage_text = columns[2].text_input("درصد تغییر", value="", placeholder="تکمیل شود", key="multi_general_percentage")
            submitted = columns[3].form_submit_button("افزودن قاعده", type="primary")
        st.markdown("</div>", unsafe_allow_html=True)
        if submitted:
            try:
                if indicator is None:
                    raise ValueError("شاخص را انتخاب کنید.")
                percentage = _parse_percentage_input(percentage_text)
            except ValueError as exc:
                st.error(str(exc))
            else:
                rules.append({"indicator_key": indicator, "direction": direction, "percentage": percentage})
                invalidate_multi_branch_result(workspace)
                st.rerun()
    else:
        st.success("برای هر ۸ شاخص قاعده عمومی تعریف شده است.")
    _rule_cards(rules, "general", workspace)


def _rule_cards(rules: list[dict], prefix: str, workspace: dict) -> None:
    if not rules:
        st.markdown('<div class="multi-branch-empty">هنوز قاعده‌ای ثبت نشده است.</div>', unsafe_allow_html=True)
        return
    st.markdown('<section class="multi-rule-list">', unsafe_allow_html=True)
    for index, rule in enumerate(list(rules)):
        direction = "افزایش" if rule["direction"] == "increase" else "کاهش"
        st.markdown(
            '<article class="multi-rule-row navy">'
            f'<strong>{html.escape(INDICATOR_REGISTRY[rule["indicator_key"]].display_name)}</strong>'
            '<span class="rule-badge">قاعده عمومی</span>'
            f'<span>{html.escape(direction)}</span>'
            f'<b dir="ltr">{html.escape(format_persian_number(rule["percentage"], 2).rstrip("۰").rstrip("٫"))}٪</b>'
            '</article>',
            unsafe_allow_html=True,
        )
        if _delete_button("حذف", f"{prefix}_delete_{index}"):
            rules.pop(index)
            invalidate_multi_branch_result(workspace)
            st.rerun()
    st.markdown("</section>", unsafe_allow_html=True)


def _exceptions(workspace: dict, data: pd.DataFrame) -> None:
    _stage_header(
        MultiBranchStage.BRANCH_EXCEPTIONS,
        "قاعده اختصاصی فقط برای همان ترکیب شعبه و شاخص، جایگزین قاعده عمومی می‌شود.",
    )
    ids, names = _branch_maps(data)
    exceptions: dict[str, list[dict]] = workspace["branch_exceptions"]
    branch = st.selectbox(
        "شعبه استثنا",
        [None, *ids],
        index=0,
        format_func=lambda item: "انتخاب شعبه" if item is None else branch_select_label(item, names),
        key="multi_exception_branch",
    )
    available_exception_indicators = get_available_exception_indicator_keys(
        list(INDICATOR_REGISTRY), exceptions, branch
    )
    indicator_options = [None, *available_exception_indicators] if available_exception_indicators else [None]
    branch_state_key = str(branch) if branch is not None else ""
    if st.session_state.get("multi_exception_branch_seen") != branch_state_key:
        current_indicator = st.session_state.get("multi_exception_indicator")
        if current_indicator not in indicator_options:
            st.session_state["multi_exception_indicator"] = None
        st.session_state["multi_exception_branch_seen"] = branch_state_key
    with st.form("multi_exception_form"):
        columns = st.columns([1.4, 1, 1])
        indicator = columns[0].selectbox(
            "شاخص",
            indicator_options,
            index=0,
            format_func=lambda key: "انتخاب شاخص" if key is None else INDICATOR_REGISTRY[key].display_name,
            disabled=not available_exception_indicators,
            key="multi_exception_indicator",
        )
        direction = columns[1].radio(
            "جهت", ("increase", "decrease"),
            format_func=lambda value: "افزایش" if value == "increase" else "کاهش",
            horizontal=True,
            key="multi_exception_direction",
        )
        percentage_text = columns[2].text_input("درصد اختصاصی", value="", placeholder="تکمیل شود", key="multi_exception_percentage")
        submitted = st.form_submit_button("افزودن استثنا", type="primary", disabled=not available_exception_indicators)
    general_keys = {rule["indicator_key"] for rule in workspace["general_rules"]}
    if indicator in general_keys:
        st.info("این استثنا جایگزین قاعده عمومی خواهد شد.")
    if submitted:
        try:
            if branch is None:
                raise ValueError("شعبه استثنا را انتخاب کنید.")
            if indicator is None:
                raise ValueError("شاخص را انتخاب کنید.")
            if _has_exception_rule(exceptions, branch, indicator):
                raise ValueError("برای این شعبه و شاخص قبلاً استثنا ثبت شده است.")
            percentage = _parse_percentage_input(percentage_text)
        except ValueError as exc:
            st.error(str(exc))
        else:
            exceptions.setdefault(str(branch), []).append(
                {"indicator_key": indicator, "direction": direction, "percentage": percentage}
            )
            invalidate_multi_branch_result(workspace)
            st.rerun()
    if not exceptions:
        st.markdown('<div class="multi-branch-empty">ثبت استثنا اختیاری است.</div>', unsafe_allow_html=True)
    for branch_code in list(exceptions):
        with st.expander(branch_select_label(branch_code, names), expanded=True):
            _rule_cards(exceptions[branch_code], f"exception_{branch_code}", workspace)
            if not exceptions[branch_code]:
                exceptions.pop(branch_code, None)


def _primary_overrides(workspace: dict, data: pd.DataFrame) -> None:
    _stage_header(
        MultiBranchStage.PRIMARY_BRANCH_OVERRIDES,
        "در صورت نیاز، مقدار نهایی شاخص‌های شعبه اصلی را با سه روش فعلی سامانه تعیین کنید.",
    )
    branch_code = str(workspace["primary_branch_code"])
    row = data.loc[data[BRANCH_ID].astype(str).eq(branch_code)].iloc[0]
    st.markdown(
        '<div class="multi-primary-identity">'
        f'<strong>شعبه اصلی: {html.escape(str(row[BRANCH_NAME]))}</strong>'
        f'<span>کد <b dir="ltr">{html.escape(persian_digits(branch_code))}</b></span></div>',
        unsafe_allow_html=True,
    )
    overrides: dict[str, dict] = workspace["primary_branch_overrides"]
    with st.form("multi_primary_override_form"):
        columns = st.columns([1.5, 1.2, 0.9, 1])
        available = [key for key in INDICATOR_REGISTRY if key not in overrides]
        indicator_options = [None, *available] if available else [None]
        indicator = columns[0].selectbox(
            "شاخص شعبه اصلی",
            indicator_options,
            index=0,
            format_func=lambda key: "انتخاب شاخص" if key is None else INDICATOR_REGISTRY[key].display_name,
            disabled=not available,
            key="multi_primary_indicator",
        )
        mode = columns[1].selectbox(
            "روش ورود", ("percent", "absolute", "final"),
            format_func={"percent": "تغییر درصدی", "absolute": "تغییر مطلق", "final": "مقدار نهایی"}.get,
            key="multi_primary_mode",
        )
        percent_direction = columns[2].radio(
            "جهت درصدی",
            ("increase", "decrease"),
            format_func={"increase": "افزایش", "decrease": "کاهش"}.get,
            horizontal=True,
            disabled=mode != "percent",
            key="multi_primary_direction",
        )
        value_text = columns[3].text_input("مقدار", value="", placeholder="تکمیل شود", key="multi_primary_value")
        submitted = st.form_submit_button("ثبت مقدار شعبه اصلی", type="primary", disabled=not available)
    if submitted:
        try:
            if indicator is None:
                raise ValueError("شاخص شعبه اصلی را انتخاب کنید.")
            entered = (
                _parse_percentage_input(value_text) * _direction_sign(percent_direction)
                if mode == "percent" else parse_raw_input_value(value_text)
            )
            baseline = float(row[indicator])
            resolved = baseline * (1 + entered / 100) if mode == "percent" else baseline + entered if mode == "absolute" else entered
            if INDICATOR_REGISTRY[indicator].minimum_value is not None and resolved < INDICATOR_REGISTRY[indicator].minimum_value:
                raise ValueError("مقدار منفی برای این شاخص مجاز نیست.")
        except ValueError as exc:
            st.error(str(exc))
        else:
            overrides[indicator] = {"input_mode": mode, "input_value": float(entered), "resolved_raw_value": float(resolved)}
            invalidate_multi_branch_result(workspace)
            st.rerun()
    if not overrides:
        st.markdown('<div class="multi-branch-empty">ثبت مقدار اختصاصی برای شعبه اصلی اختیاری است.</div>', unsafe_allow_html=True)
    for index, (indicator, item) in enumerate(list(overrides.items())):
        summary = _primary_rule_summary(indicator, item, float(row[indicator]))
        st.markdown(_render_primary_rule_card(summary), unsafe_allow_html=True)
        if _delete_button("حذف", f"primary_delete_{index}"):
            overrides.pop(indicator)
            invalidate_multi_branch_result(workspace)
            st.rerun()


def _build_scenario(
    workspace: dict, branch_count: int, actor: ActorContext
) -> MultiBranchScenarioV1:
    now = datetime.now()
    return MultiBranchScenarioV1(
        scenario_id=str(uuid.uuid4()),
        scenario_name=str(workspace["scenario_name"]).strip(),
        created_at=now,
        updated_at=now,
        actor_context=actor,
        primary_branch_code=str(workspace["primary_branch_code"]),
        population_definition=PopulationDefinition("official-ranking-population", workspace["period"], branch_count),
        general_rules=tuple(
            PercentageRule(row["indicator_key"], PercentageDirection(row["direction"]), row["percentage"])
            for row in workspace["general_rules"]
        ),
        branch_exceptions=tuple(
            BranchException(branch, tuple(
                PercentageRule(row["indicator_key"], PercentageDirection(row["direction"]), row["percentage"])
                for row in rules
            ))
            for branch, rules in workspace["branch_exceptions"].items()
        ),
        primary_branch_overrides=tuple(
            PrimaryBranchOverride(key, row["input_mode"], row["input_value"], row["resolved_raw_value"])
            for key, row in workspace["primary_branch_overrides"].items()
        ),
    )


def _review(
    workspace: dict, data: pd.DataFrame, baseline_outputs, actor: ActorContext
) -> None:
    names = data.assign(**{BRANCH_ID: data[BRANCH_ID].astype(str)}).set_index(BRANCH_ID)[BRANCH_NAME].astype(str).to_dict()
    primary = str(workspace["primary_branch_code"])
    primary_row = data.loc[data[BRANCH_ID].astype(str).eq(primary)].iloc[0]
    exception_rules = sum(len(items) for items in workspace["branch_exceptions"].values())
    overview = (
        '<section class="multi-review-hero"><header><h2>بازبینی نهایی سناریو</h2>'
        '<p>پیش از اجرای مدل رسمی، دامنه و تمام تغییرات سناریو را کنترل کنید.</p></header>'
        '<div class="multi-review-overview"><div class="identity">'
        f'<small>نام سناریو</small><h3>{html.escape(str(workspace["scenario_name"]))}</h3>'
        f'<span>شعبه اصلی: {html.escape(names.get(primary, primary))}</span>'
        f'<span>کد شعبه: <b dir="ltr">{html.escape(persian_digits(primary))}</b></span></div>'
        '<div class="counts">'
        f'{_review_fact("جامعه (کل شعب)", f"{format_persian_number(len(data), 0)} شعبه")}'
        f'{_review_fact("قواعد عمومی", format_persian_number(len(workspace["general_rules"]), 0))}'
        f'{_review_fact("استثناهای شعب", format_persian_number(exception_rules, 0))}'
        f'{_review_fact("مقادیر شعبه اصلی", format_persian_number(len(workspace["primary_branch_overrides"]), 0))}'
        '</div></div></section>'
    )
    families = (
        '<section class="multi-review-family-grid">'
        f'<article class="navy"><b>◎</b><h3>قواعد عمومی</h3>{_ltr_value(format_persian_number(len(workspace["general_rules"]), 0))}<p>قاعده پایه برای جامعه (کل شعب)</p></article>'
        f'<article class="amber"><b>◇</b><h3>استثناهای شعب</h3>{_ltr_value(format_persian_number(exception_rules, 0))}<p>جایگزین قاعده عمومی در شعب منتخب</p></article>'
        f'<article class="purple"><b>◉</b><h3>مقادیر اختصاصی شعبه اصلی</h3>{_ltr_value(format_persian_number(len(workspace["primary_branch_overrides"]), 0))}<p>بالاترین اولویت برای شعبه اصلی</p></article>'
        '</section>'
    )
    st.markdown(overview + families, unsafe_allow_html=True)

    if not workspace["general_rules"]:
        general_body = '<div class="multi-branch-empty">قاعده عمومی ثبت نشده است.</div>'
    else:
        general_body = "".join(_render_review_rule_card(rule, len(data)) for rule in workspace["general_rules"])
    st.markdown(_review_section_html("قواعد عمومی", general_body, "general"), unsafe_allow_html=True)

    general_keys = {rule["indicator_key"] for rule in workspace["general_rules"]}
    exception_cards = [
        _render_exception_card(branch_code, rule, names, general_keys)
        for branch_code, rules in workspace["branch_exceptions"].items()
        for rule in rules
    ]
    if not exception_cards:
        exception_body = '<div class="multi-branch-empty">استثنای شعبه‌ای ثبت نشده است.</div>'
    else:
        exception_body = "".join(exception_cards)
    st.markdown(_review_section_html("استثناهای شعب", exception_body, "exception"), unsafe_allow_html=True)

    primary_cards = [_render_primary_rule_card(row) for row in _primary_rule_rows(workspace["primary_branch_overrides"], primary_row).to_dict("records")]
    if not primary_cards:
        primary_body = '<div class="multi-branch-empty">مقدار اختصاصی برای شعبه اصلی ثبت نشده است.</div>'
    else:
        primary_body = "".join(primary_cards)
    st.markdown(_review_section_html("مقادیر اختصاصی شعبه اصلی", primary_body, "primary"), unsafe_allow_html=True)

    st.markdown(
        '<section class="multi-precedence"><div><span>مقدار مبنا</span><i>←</i><span>قاعده عمومی</span><i>←</i><span>استثنای شعبه</span><i>←</i><span>مقدار اختصاصی شعبه اصلی</span></div>'
        '<p>در صورت وجود چند قاعده برای یک شاخص، مقدار اختصاصی شعبه اصلی بالاترین اولویت را دارد؛ سپس استثنای شعبه، قاعده عمومی و در نهایت مقدار مبنا اعمال می‌شود.</p></section>'
        '<div class="multi-execution-bar"></div>',
        unsafe_allow_html=True,
    )
    actions = st.columns([1.2, 1.8, 4])
    if actions[0].button("بازگشت و ویرایش", width="stretch"):
        move_to_multi_branch_stage(workspace, MultiBranchStage.PRIMARY_BRANCH_OVERRIDES)
        st.rerun()
    with actions[1]:
        if st.button("اجرای سناریو با مدل رسمی", type="primary", width="stretch"):
            try:
                scenario = _build_scenario(workspace, len(data), actor)
                resolved = MultiBranchRuleResolver.resolve(scenario, data)
                scenario_outputs = run_ranking_model(resolved.scenario_data)
                comparison = compare_model_outputs(baseline_outputs, scenario_outputs)
            except (ValueError, MultiBranchRuleValidationError) as exc:
                st.error(str(exc))
            else:
                workspace["execution_result"] = {
                    "scenario": scenario,
                    "resolved": resolved,
                    "outputs": scenario_outputs,
                    "comparison": comparison,
                }
                workspace["show_result"] = True
                st.rerun()


def _persistence_error(exc: Exception) -> None:
    if isinstance(exc, ConcurrencyError):
        st.error("این سناریو در نشست دیگری تغییر کرده است. نسخه ذخیره‌شده را دوباره باز کنید.")
    elif isinstance(exc, (ScenarioPersistenceError, ValueError)):
        st.error(str(exc))
    else:
        st.error("عملیات ذخیره‌سازی انجام نشد. لطفاً دوباره تلاش کنید.")


def _save_draft(
    workspace: dict, service: MultiBranchWorkspaceService, *, save_as_new: bool = False
) -> None:
    if not str(workspace.get("scenario_name") or "").strip():
        st.error("برای ذخیره پیش‌نویس، نام سناریو را وارد کنید.")
        return
    try:
        record = service.save_draft(workspace, save_as_new=save_as_new)
    except Exception as exc:
        _persistence_error(exc)
    else:
        st.session_state["saved_scenarios_refresh_token"] = record.updated_at.isoformat()
        messages = {
            "created": "سناریو با موفقیت ذخیره شد.",
            "updated": "تغییرات سناریو با موفقیت به‌روزرسانی شد.",
            "version": "نسخه جدید سناریو با موفقیت ایجاد شد.",
        }
        st.success(f"{messages.get(workspace.get('last_save_action'), 'سناریو با موفقیت ذخیره شد.')} (نسخه {record.row_version})")


def _persistence_bar(workspace: dict, service: MultiBranchWorkspaceService) -> None:
    persisted = dict(workspace.get("persistence") or {})
    dirty = service.has_unsaved_changes(workspace)
    status = persisted.get("status")
    if not persisted.get("scenario_id"):
        label = "ذخیره‌نشده"
    elif dirty:
        label = "دارای تغییرات ذخیره‌نشده"
    elif status == "executed":
        label = "نتیجه رسمی ذخیره‌شده"
    else:
        label = "پیش‌نویس ذخیره‌شده"
    columns = st.columns([3.8, 1.2, 1.45])
    columns[0].caption(
        f"وضعیت: {label}"
        + (f" · نسخه {persisted.get('version_number', 1)}" if persisted.get("scenario_id") else "")
    )
    if columns[1].button("ذخیره پیش‌نویس", key="multi_save_draft", width="stretch"):
        _save_draft(workspace, service)
    if columns[2].button(
        "ذخیره به‌عنوان نسخه جدید",
        key="multi_save_new_version",
        disabled=not bool(persisted.get("scenario_id")),
        width="stretch",
    ):
        _save_draft(workspace, service, save_as_new=True)


def _result(
    workspace: dict, data: pd.DataFrame, service: MultiBranchWorkspaceService
) -> None:
    result = workspace["execution_result"]
    scenario = result["scenario"]
    manifest = result["resolved"].manifest
    changed = [item for item in manifest if item.changed]
    exception_rules = sum(len(item.indicator_rules) for item in scenario.branch_exceptions)
    primary_name = data.assign(**{BRANCH_ID: data[BRANCH_ID].astype(str)}).set_index(BRANCH_ID)[BRANCH_NAME].astype(str).to_dict().get(str(scenario.primary_branch_code), "—")
    render_multi_branch_results(
        result["comparison"],
        manifest,
        scenario.primary_branch_code,
        context={
            "نام سناریو": scenario.scenario_name,
            "وضعیت اجرا": "اجرا شده",
            "جامعه (کل شعب)": f"{format_persian_number(scenario.population_definition.expected_branch_count, 0)} شعبه",
            "شعبه اصلی": f"{primary_name} ({persian_digits(scenario.primary_branch_code)})",
            "قواعد عمومی": format_persian_number(len(scenario.general_rules), 0),
            "استثناهای شعب": format_persian_number(exception_rules, 0),
            "مقادیر اختصاصی شعبه اصلی": format_persian_number(len(scenario.primary_branch_overrides), 0),
            "زمان اجرا": scenario.calculation_metadata.calculated_at if scenario.calculation_metadata else datetime.now().strftime("%Y-%m-%d %H:%M"),
            "تعداد تغییرات شعبه–شاخص": format_persian_number(len(changed), 0),
        },
    )
    actions = st.columns([1.5, 1.5, 4])
    if actions[0].button("ذخیره نتیجه رسمی", type="primary", width="stretch"):
        try:
            record = service.save_execution(workspace, data=data)
        except Exception as exc:
            _persistence_error(exc)
        else:
            st.session_state["saved_scenarios_refresh_token"] = record.updated_at.isoformat()
            st.success(f"نتیجه رسمی ذخیره شد (نسخه رکورد {record.row_version}).")
    if actions[1].button("بازگشت و ویرایش", width="stretch"):
        workspace["show_result"] = False
        st.rerun()


def _persisted_result(workspace: dict, data: pd.DataFrame) -> None:
    """Show the immutable saved snapshot before an optional current-model rerun."""
    results = list(workspace.get("persisted_result_summaries") or [])
    names = data.assign(**{BRANCH_ID: data[BRANCH_ID].astype(str)}).set_index(BRANCH_ID)[BRANCH_NAME].astype(str).to_dict()
    primary = str(workspace.get("primary_branch_code") or "")
    table = pd.DataFrame([
        {
            BRANCH_ID: item.branch_id,
            BRANCH_NAME: names.get(item.branch_id, "—"),
            "baseline_score": item.baseline_score,
            "scenario_score": item.scenario_score,
            "score_change": item.score_change,
            "baseline_rank": item.baseline_rank,
            "scenario_rank": item.scenario_rank,
            "rank_change": item.rank_change,
            "baseline_grade": item.baseline_grade,
            "scenario_grade": item.scenario_grade,
        }
        for item in results
    ])
    render_multi_branch_results(
        SimpleNamespace(branch_comparison=table),
        (),
        primary,
        context={
            "نام سناریو": workspace["scenario_name"],
            "وضعیت اجرا": "نتیجه رسمی ذخیره‌شده",
            "جامعه (کل شعب)": f"{format_persian_number(len(results), 0)} شعبه",
            "شعبه اصلی": f"{names.get(primary, '—')} ({persian_digits(primary)})" if primary else "—",
            "قواعد عمومی": format_persian_number(len(workspace.get("general_rules") or []), 0),
            "استثناهای شعب": format_persian_number(sum(len(items) for items in (workspace.get("branch_exceptions") or {}).values()), 0),
            "مقادیر اختصاصی شعبه اصلی": format_persian_number(len(workspace.get("primary_branch_overrides") or {}), 0),
        },
        audit_available=False,
    )
    st.caption("این Snapshot رسمی زمان ذخیره است. اجرای مجدد، نتیجه را با داده و مدل جاری محاسبه می‌کند.")
    if st.button("ویرایش یا اجرای مجدد سناریو", type="primary"):
        workspace["show_persisted_result"] = False
        workspace["current_stage"] = MultiBranchStage.REVIEW.value
        st.rerun()


def _can_advance(stage: MultiBranchStage, workspace: dict) -> tuple[bool, str | None]:
    if stage is MultiBranchStage.SCENARIO_DETAILS:
        if not str(workspace.get("scenario_name") or "").strip():
            return False, "نام سناریو را وارد کنید."
        if not workspace.get("primary_branch_code"):
            return False, "شعبه اصلی را انتخاب کنید."
    return True, None


def _navigation(stage: MultiBranchStage, workspace: dict) -> None:
    if stage is MultiBranchStage.REVIEW:
        return
    index = MULTI_BRANCH_STAGE_ORDER.index(stage)
    columns = st.columns([1.2, 1.2, 5])
    if columns[0].button("مرحله بعد", type="primary", disabled=index == len(MULTI_BRANCH_STAGE_ORDER) - 1, width="stretch"):
        allowed, message = _can_advance(stage, workspace)
        if not allowed:
            st.error(message)
        else:
            move_to_multi_branch_stage(workspace, MULTI_BRANCH_STAGE_ORDER[index + 1])
            st.rerun()
    if columns[1].button("مرحله قبل", disabled=index == 0, width="stretch"):
        move_to_multi_branch_stage(workspace, MULTI_BRANCH_STAGE_ORDER[index - 1])
        st.rerun()


def render_multi_branch_workspace(
    data: pd.DataFrame,
    baseline_outputs,
    current_user: CurrentUser,
    persistence_service: MultiBranchWorkspaceService,
) -> None:
    """Render the isolated multi-branch workflow in the existing application shell."""
    workspace = initialize_multi_branch_state(st.session_state)
    actor = _actor_context(current_user)
    st.markdown('<div class="multi-branch-page" data-multi-branch-page="true">', unsafe_allow_html=True)
    _scroll_to_top_once(workspace)
    st.markdown(
        '<header class="scenario-builder-header"><span class="scenario-builder-header-icon">'
        f'{icon_svg("buildings")}</span><div><h1>سناریوی چندشعبه‌ای</h1>'
        '<p>تعریف قواعد شبکه، استثناهای شعب و مقادیر اختصاصی شعبه اصلی</p></div></header>',
        unsafe_allow_html=True,
    )
    if workspace.get("entry_source") == "saved":
        st.info("سناریوی ذخیره‌شده بازیابی شد؛ قواعد، استثناها و مقادیر شعبه اصلی برای ادامه کار آماده‌اند.")
        workspace["entry_source"] = "active"
    for warning in workspace.pop("restore_warnings", []):
        st.warning(warning)
    _persistence_bar(workspace, persistence_service)
    if workspace.get("show_persisted_result") and workspace.get("persisted_result_summaries"):
        _persisted_result(workspace, data)
        st.markdown("</div>", unsafe_allow_html=True)
        return
    if workspace.get("show_result") and workspace.get("execution_result"):
        _result(workspace, data, persistence_service)
        st.markdown("</div>", unsafe_allow_html=True)
        return
    stage = current_multi_branch_stage(workspace)
    _workflow(stage)
    if stage is MultiBranchStage.SCENARIO_DETAILS:
        _details(workspace, data, actor)
    elif stage is MultiBranchStage.GENERAL_RULES:
        _rule_editor(workspace)
    elif stage is MultiBranchStage.BRANCH_EXCEPTIONS:
        _exceptions(workspace, data)
    elif stage is MultiBranchStage.PRIMARY_BRANCH_OVERRIDES:
        _primary_overrides(workspace, data)
    else:
        _review(workspace, data, baseline_outputs, actor)
    _navigation(stage, workspace)
    st.markdown("</div>", unsafe_allow_html=True)
