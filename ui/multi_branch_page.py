"""Dedicated five-stage multi-branch scenario workspace."""

from __future__ import annotations

from datetime import datetime
import html
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
from ui.formatters import format_persian_number, parse_raw_input_value, persian_digits
from ui.multi_branch_state import (
    MULTI_BRANCH_STAGE_LABELS,
    MULTI_BRANCH_STAGE_ORDER,
    MultiBranchStage,
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
        can_select_primary_branch=not bool(assigned_branch),
    )


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
        if actor.can_select_primary_branch:
            current = workspace.get("primary_branch_code")
            index = ids.index(str(current)) + 1 if current is not None and str(current) in ids else 0
            selected = columns[1].selectbox(
                "شعبه اصلی",
                [None, *ids],
                index=index,
                format_func=lambda item: branch_select_label(item, names),
                key="multi_branch_primary",
            )
            workspace["primary_branch_code"] = resolve_primary_branch(
                actor, str(selected) if selected is not None else None
            )
        else:
            assigned = resolve_primary_branch(actor, None)
            if assigned not in ids:
                st.error("شعبه تخصیص‌یافته کاربر در جامعه رسمی رتبه‌بندی وجود ندارد.")
                workspace["primary_branch_code"] = None
            else:
                workspace["primary_branch_code"] = assigned
                columns[1].text_input(
                    "شعبه اصلی",
                    value=branch_select_label(assigned, names),
                    disabled=True,
                    key="multi_branch_assigned_primary",
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
        with st.form("multi_general_rule_form", clear_on_submit=True):
            columns = st.columns([1.6, 1, 1])
            indicator = columns[0].selectbox(
                "شاخص", available, format_func=lambda key: INDICATOR_REGISTRY[key].display_name
            )
            direction = columns[1].radio(
                "جهت تغییر", ("increase", "decrease"),
                format_func=lambda value: "افزایش" if value == "increase" else "کاهش",
                horizontal=True,
            )
            percentage = columns[2].number_input("درصد تغییر", min_value=0.0, value=0.0, step=1.0)
            submitted = st.form_submit_button("افزودن قاعده عمومی", type="primary")
        if submitted:
            rules.append({"indicator_key": indicator, "direction": direction, "percentage": float(percentage)})
            invalidate_multi_branch_result(workspace)
            st.rerun()
    else:
        st.success("برای هر ۸ شاخص قاعده عمومی تعریف شده است.")
    _rule_cards(rules, "general", workspace)


def _rule_cards(rules: list[dict], prefix: str, workspace: dict) -> None:
    if not rules:
        st.markdown('<div class="multi-branch-empty">هنوز قاعده‌ای ثبت نشده است.</div>', unsafe_allow_html=True)
        return
    for index, rule in enumerate(list(rules)):
        direction = "افزایش" if rule["direction"] == "increase" else "کاهش"
        columns = st.columns([3, 1.2, 1, 0.65])
        columns[0].markdown(f"**{INDICATOR_REGISTRY[rule['indicator_key']].display_name}**")
        columns[1].write(direction)
        columns[2].write(f"{format_persian_number(rule['percentage'], 1)}٪")
        if columns[3].button("حذف", key=f"{prefix}_delete_{index}"):
            rules.pop(index)
            invalidate_multi_branch_result(workspace)
            st.rerun()


def _exceptions(workspace: dict, data: pd.DataFrame) -> None:
    _stage_header(
        MultiBranchStage.BRANCH_EXCEPTIONS,
        "قاعده اختصاصی فقط برای همان ترکیب شعبه و شاخص، جایگزین قاعده عمومی می‌شود.",
    )
    ids, names = _branch_maps(data)
    exceptions: dict[str, list[dict]] = workspace["branch_exceptions"]
    with st.form("multi_exception_form", clear_on_submit=True):
        columns = st.columns([1.6, 1.4, 1, 1])
        branch = columns[0].selectbox("شعبه استثنا", ids, format_func=lambda item: branch_select_label(item, names))
        occupied = {row["indicator_key"] for row in exceptions.get(branch, [])}
        available = [key for key in INDICATOR_REGISTRY if key not in occupied]
        indicator = columns[1].selectbox(
            "شاخص", available or list(INDICATOR_REGISTRY),
            format_func=lambda key: INDICATOR_REGISTRY[key].display_name,
            disabled=not available,
        )
        direction = columns[2].radio(
            "جهت", ("increase", "decrease"),
            format_func=lambda value: "افزایش" if value == "increase" else "کاهش",
            horizontal=True,
        )
        percentage = columns[3].number_input("درصد اختصاصی", min_value=0.0, value=0.0, step=1.0)
        submitted = st.form_submit_button("افزودن استثنا", type="primary", disabled=not available)
    if submitted:
        exceptions.setdefault(branch, []).append(
            {"indicator_key": indicator, "direction": direction, "percentage": float(percentage)}
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
    overrides: dict[str, dict] = workspace["primary_branch_overrides"]
    with st.form("multi_primary_override_form", clear_on_submit=True):
        columns = st.columns([1.5, 1.2, 1])
        available = [key for key in INDICATOR_REGISTRY if key not in overrides]
        indicator = columns[0].selectbox(
            "شاخص شعبه اصلی", available or list(INDICATOR_REGISTRY),
            format_func=lambda key: INDICATOR_REGISTRY[key].display_name, disabled=not available,
        )
        mode = columns[1].selectbox(
            "روش ورود", ("percent", "absolute", "final"),
            format_func={"percent": "تغییر درصدی", "absolute": "تغییر مطلق", "final": "مقدار نهایی"}.get,
        )
        value_text = columns[2].text_input("مقدار", value="0")
        submitted = st.form_submit_button("ثبت مقدار شعبه اصلی", type="primary", disabled=not available)
    if submitted:
        try:
            entered = parse_raw_input_value(value_text)
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
        columns = st.columns([2.2, 1.2, 1.4, 0.65])
        columns[0].markdown(f"**{INDICATOR_REGISTRY[indicator].display_name}**")
        columns[1].write({"percent": "درصدی", "absolute": "مطلق", "final": "نهایی"}[item["input_mode"]])
        columns[2].write(f"مقدار سناریو: {format_persian_number(item['resolved_raw_value'], 0)}")
        if columns[3].button("حذف", key=f"primary_delete_{index}"):
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
    _stage_header(MultiBranchStage.REVIEW, "تعریف سناریو را بازبینی و سپس با موتور رسمی درجه‌بندی اجرا کنید.")
    exception_rules = sum(len(items) for items in workspace["branch_exceptions"].values())
    cards = st.columns(4)
    cards[0].metric("شعب جامعه محاسبه", format_persian_number(len(data), 0))
    cards[1].metric("قواعد عمومی", format_persian_number(len(workspace["general_rules"]), 0))
    cards[2].metric("قواعد استثنا", format_persian_number(exception_rules, 0))
    cards[3].metric("مقادیر شعبه اصلی", format_persian_number(len(workspace["primary_branch_overrides"]), 0))
    st.caption("تقدم محاسباتی: مقدار شعبه اصلی ← استثنای شعبه ← قاعده عمومی ← مقدار مبنا")
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
        action = "نسخه جدید" if save_as_new else "پیش‌نویس"
        st.success(f"{action} با موفقیت ذخیره شد (نسخه {record.row_version}).")


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
    st.success(f"سناریوی «{scenario.scenario_name}» با موفقیت روی کل جامعه رسمی اجرا شد.")
    cards = st.columns(4)
    cards[0].metric("کل شعب", format_persian_number(scenario.population_definition.expected_branch_count, 0))
    cards[1].metric("تغییرات مؤثر", format_persian_number(len(changed), 0))
    cards[2].metric("شعب دارای تغییر", format_persian_number(len({item.branch_code for item in changed}), 0))
    cards[3].metric("شعبه اصلی", persian_digits(scenario.primary_branch_code))
    render_multi_branch_results(
        result["comparison"],
        manifest,
        scenario.primary_branch_code,
    )
    actions = st.columns([1.5, 1.5, 4])
    if actions[0].button("ذخیره نتیجه رسمی", type="primary", width="stretch"):
        try:
            record = service.save_execution(workspace, data=data)
        except Exception as exc:
            _persistence_error(exc)
        else:
            st.success(f"نتیجه رسمی ذخیره شد (نسخه رکورد {record.row_version}).")
    if actions[1].button("بازگشت و ویرایش", width="stretch"):
        workspace["show_result"] = False
        st.rerun()


def _persisted_result(workspace: dict, data: pd.DataFrame) -> None:
    """Show the immutable saved snapshot before an optional current-model rerun."""
    results = list(workspace.get("persisted_result_summaries") or [])
    names = data.assign(**{BRANCH_ID: data[BRANCH_ID].astype(str)}).set_index(BRANCH_ID)[BRANCH_NAME].astype(str).to_dict()
    primary = str(workspace.get("primary_branch_code") or "")
    primary_result = next((item for item in results if item.branch_id == primary), None)
    st.success(f"نتیجه رسمی ذخیره‌شده سناریوی «{workspace['scenario_name']}» بازیابی شد.")
    cards = st.columns(4)
    cards[0].metric("تعداد شعب نتیجه", format_persian_number(len(results), 0))
    cards[1].metric("شعب صعودکرده", format_persian_number(sum(item.rank_change > 0 for item in results), 0))
    cards[2].metric("شعب نزول‌کرده", format_persian_number(sum(item.rank_change < 0 for item in results), 0))
    cards[3].metric(
        "رتبه ذخیره‌شده شعبه اصلی",
        format_persian_number(primary_result.scenario_rank, 0) if primary_result else "—",
    )
    table = pd.DataFrame([
        {
            "کد شعبه": item.branch_id,
            "نام شعبه": names.get(item.branch_id, "—"),
            "رتبه مبنا": item.baseline_rank,
            "رتبه سناریو": item.scenario_rank,
            "تغییر رتبه": item.rank_change,
            "امتیاز مبنا": item.baseline_score,
            "امتیاز سناریو": item.scenario_score,
            "تغییر امتیاز": item.score_change,
            "درجه مبنا": item.baseline_grade,
            "درجه سناریو": item.scenario_grade,
        }
        for item in results
    ])
    st.dataframe(table, width="stretch", height=520, hide_index=True)
    st.caption("این جدول Snapshot رسمی زمان ذخیره است. اجرای مجدد، نتیجه را با داده و مدل جاری محاسبه می‌کند.")
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
