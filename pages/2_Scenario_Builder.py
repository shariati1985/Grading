"""Complete interactive sensitivity-analysis Scenario Builder."""

from __future__ import annotations

from pathlib import Path
from typing import Final
from uuid import NAMESPACE_URL, uuid4, uuid5

import pandas as pd
import streamlit as st

from engine.ranking_engine import BRANCH_ID, BRANCH_NAME, REGION, ModelOutputs
from engine.indicator_registry import INDICATOR_REGISTRY
from engine.scenario_rule_engine import (
    IndicatorRule,
    RuleOperation,
    RulePreview,
    ScenarioRuleEngine,
)
from persistence.contracts import ConcurrencyError, ScenarioPersistenceError
from persistence.models import ScenarioRecord
from services.factory import create_local_scenario_service
from services.focus_branch import resolve_focus_branch, scenario_mode_labels
from services.scenario_management_service import ScenarioManagementService
from services.selection_scope import (
    SelectionResolutionError,
    SelectionResolver,
    SelectionScope,
)
from ui import initialize_session_state
from ui.branch_navigation import adjacent_branch_id, retain_selected_branch
from ui.manual_override_state import (
    ManualOverrideRow,
    NO_CHANGE_LABEL,
    RULE_UI_OPTIONS,
    delete_override_group,
    domain_rule_to_ui,
    duplicate_override_keys,
    new_override_row,
    normalize_rule_widget_state,
    serialize_override_rows,
    to_domain_overrides,
    replace_override_group,
    ui_rule_to_domain,
)
from ui.components import (
    render_empty_state,
    render_kpi_card,
    render_kpi_group,
    render_page_header,
)
from ui.charts import (
    build_indicator_rank_lollipop,
    build_network_rank_chart,
    build_selected_indicator_score_chart,
    prepare_selected_indicator_scores,
    prepare_network_rank_changes,
    render_chart,
    validate_indicator_score_chart_matches_table,
)
from ui.data_access import load_dashboard_data
from ui.formatters import (
    format_grade,
    format_number,
    format_percentage,
    format_rank,
    format_rank_change,
    format_raw_value,
    format_score,
)
from ui.scenario_workflow import (
    INDICATOR_LABELS,
    INDICATOR_ORDER,
    NETWORK_FILTERS,
    build_editor_data,
    build_indicator_editor_state,
    build_scenario_changes_from_editor_state,
    calculate_change_percent,
    calculate_scenario_value,
    editor_edit_modes,
    execute_scenario_from_editor_state,
    execute_generated_changes,
    filter_network_impact,
    indicator_widget_key,
    reset_scenario_state,
    reset_all_indicator_rows,
    reset_indicator_row,
    restore_indicator_editor_state,
    selected_branch_results,
    update_indicator_editor_state,
)
from ui.styles import apply_global_styles
from ui.tables import (
    render_indicator_scores_table,
    render_indicator_values_table,
    render_table,
)

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
DATA_FILE: Final[Path] = ROOT / "Data.xlsx"
MODEL_PERIOD: Final[str] = "1404-04"
OTHER_SCOPE_LABELS: Final[dict[SelectionScope, str]] = {
    SelectionScope.SELECTED_BRANCHES: "شعب منتخب",
    SelectionScope.SELECTED_REGIONS: "مناطق منتخب",
    SelectionScope.ALL_BRANCHES: "کل شعب بانک",
}


def _prepare_rule_widgets(
    *,
    operation_key: str,
    value_key: str,
    default_label: str,
    default_value: float,
) -> bool:
    return normalize_rule_widget_state(
        st.session_state,
        operation_key=operation_key,
        value_key=value_key,
        default_label=default_label,
        default_value=default_value,
    )


def _render_focus_branch_overrides(
    baseline_df: pd.DataFrame, user_branch_id: str
) -> list[ManualOverrideRow]:
    branch = baseline_df.assign(**{BRANCH_ID: baseline_df[BRANCH_ID].astype(str)}).loc[
        lambda frame: frame[BRANCH_ID].eq(user_branch_id)
    ].iloc[0]
    group_id = str(uuid5(NAMESPACE_URL, f"user-branch-override:{user_branch_id}"))
    rows: list[ManualOverrideRow] = [
        dict(row)
        for row in st.session_state.get(
            "focus_branch_overrides",
            st.session_state.get("focus_branch_override_rows", []),
        )
    ]
    existing = {row["indicator_key"]: row for row in rows}
    assigned_focus = (
        st.session_state.get("focus_branch_source") == "ASSIGNED_USER_BRANCH"
    )
    st.markdown(
        "#### تنظیمات شعبه من" if assigned_focus else "#### تنظیمات شعبه محوری تحلیل"
    )
    st.caption(f"{branch[BRANCH_NAME]} — کد {user_branch_id} — منطقه {branch[REGION]}")
    with st.form(f"focus_branch_override_form_{group_id}"):
        for indicator_key, indicator in INDICATOR_REGISTRY.items():
            current = existing.get(indicator_key)
            if current:
                label, displayed = domain_rule_to_ui(
                    RuleOperation(current["operation"]), float(current["input_value"])
                )
            else:
                label, displayed = NO_CHANGE_LABEL, 0.0
            operation_key = f"focus_{user_branch_id}_{indicator_key}_operation"
            value_key = f"focus_{user_branch_id}_{indicator_key}_value"
            value_disabled = _prepare_rule_widgets(
                operation_key=operation_key,
                value_key=value_key,
                default_label=label,
                default_value=displayed,
            )
            columns = st.columns([2, 1.5, 1])
            with columns[0]:
                st.write(indicator.display_name)
            with columns[1]:
                option = st.selectbox(
                    f"عملیات {indicator.display_name}", RULE_UI_OPTIONS,
                    key=operation_key, label_visibility="collapsed",
                )
            with columns[2]:
                st.number_input(
                    f"مقدار {indicator.display_name}", value=0.0, key=value_key,
                    disabled=value_disabled,
                    label_visibility="collapsed",
                )
        submitted = st.form_submit_button(
            "ثبت تغییرات شعبه من"
            if assigned_focus else "ثبت تغییرات شعبه محوری تحلیل"
        )
    if submitted:
        replacement: list[ManualOverrideRow] = []
        for indicator_key in INDICATOR_REGISTRY:
            converted = ui_rule_to_domain(
                st.session_state[f"focus_{user_branch_id}_{indicator_key}_operation"],
                float(st.session_state[f"focus_{user_branch_id}_{indicator_key}_value"]),
            )
            if converted is None:
                continue
            previous = existing.get(indicator_key)
            replacement.append(
                new_override_row(
                    branch_id=user_branch_id,
                    indicator_key=indicator_key,
                    operation=converted[0],
                    input_value=converted[1],
                    group_id=group_id,
                    source="focus_branch_override",
                    row_id_factory=(
                        (lambda row_id=previous["row_id"]: row_id)
                        if previous else (lambda: str(uuid4()))
                    ),
                )
            )
        rows = replacement
        st.session_state["focus_branch_overrides"] = rows
        st.session_state["focus_branch_override_rows"] = rows
        st.success(
            "تغییرات شعبه من ثبت شد."
            if assigned_focus else "تغییرات شعبه محوری تحلیل ثبت شد."
        )
        if not rows:
            st.info("برای شعبه محوری تغییری ثبت نشده است.")
    return rows


def _render_user_only_preview(
    baseline_df: pd.DataFrame, user_branch_id: str
) -> tuple[RulePreview, dict[str, object]]:
    rows = _render_focus_branch_overrides(baseline_df, user_branch_id)
    preview = ScenarioRuleEngine.preview(
        [user_branch_id], baseline_df, [],
        to_domain_overrides(rows, default_source="focus_branch_override")
    )
    definition = {
        "schema_version": 2,
        "scenario_mode": "ONLY_USER_BRANCH",
        "focus_branch_id": user_branch_id,
        "focus_branch_source": st.session_state["focus_branch_source"],
        "selection_scope": SelectionScope.USER_BRANCH.value,
        "selection_inputs": {
            "selected_regions": [],
            "selected_branch_ids": [user_branch_id],
        },
        "bulk_rules": [],
        "network_bulk_rules": [],
        "focus_branch_overrides": serialize_override_rows(rows),
        "manual_overrides": [],
        "branch_exception_groups": {},
        "validation_status": "valid" if preview.is_valid else "invalid",
    }
    st.markdown(
        "#### تغییرات شعبه من"
        if st.session_state.get("focus_branch_source") == "ASSIGNED_USER_BRANCH"
        else "#### تغییرات شعبه محوری تحلیل"
    )
    frame = pd.DataFrame([row.__dict__ for row in preview.rows])
    if not frame.empty:
        frame = frame.loc[
            frame["final_value"].ne(frame["baseline_value"])
            | frame["validation_status"].eq("invalid")
        ]
    if frame.empty:
        st.caption("تغییری ثبت نشده است.")
    else:
        frame["change_source"] = frame["change_source"].replace(
            {"manual_override": "focus_branch_override"}
        )
        st.dataframe(frame, width="stretch", height=320)
    if preview.issues:
        st.markdown("#### خطاهای اعتبارسنجی")
        st.dataframe(pd.DataFrame([issue.__dict__ for issue in preview.issues]))
    return preview, definition


def _render_rule_preview(
    baseline_df: pd.DataFrame,
    user_branch_id: str,
    other_ids: list[str],
    service: ScenarioManagementService,
) -> tuple[RulePreview, dict[str, object]]:
    user_rows = _render_focus_branch_overrides(baseline_df, user_branch_id)
    st.markdown("#### قاعده عمومی سایر شعب")
    rules: list[IndicatorRule] = []
    for indicator_key, definition in INDICATOR_REGISTRY.items():
        operation_key = f"network_{indicator_key}_operation"
        value_key = f"network_{indicator_key}_value"
        legacy_operation_key = f"_bulk_operation_{indicator_key}"
        legacy_value_key = f"_bulk_value_{indicator_key}"
        if operation_key not in st.session_state and legacy_operation_key in st.session_state:
            st.session_state[operation_key] = st.session_state[legacy_operation_key]
        if value_key not in st.session_state and legacy_value_key in st.session_state:
            st.session_state[value_key] = st.session_state[legacy_value_key]
        value_disabled = _prepare_rule_widgets(
            operation_key=operation_key,
            value_key=value_key,
            default_label=NO_CHANGE_LABEL,
            default_value=0.0,
        )
        columns = st.columns([2, 1.5, 1])
        with columns[0]:
            st.write(definition.display_name)
        with columns[1]:
            option = st.selectbox(
                f"عملیات {definition.display_name}",
                RULE_UI_OPTIONS,
                key=operation_key,
                label_visibility="collapsed",
            )
        with columns[2]:
            value = st.number_input(
                f"مقدار {definition.display_name}",
                value=0.0,
                key=value_key,
                disabled=value_disabled,
                label_visibility="collapsed",
            )
        converted = ui_rule_to_domain(option, value)
        if converted:
            rules.append(IndicatorRule(indicator_key, *converted))

    st.markdown("#### استثناهای دستی")
    names = baseline_df.assign(**{BRANCH_ID: baseline_df[BRANCH_ID].astype(str)}).set_index(BRANCH_ID)[BRANCH_NAME].to_dict()
    branch_options = list(other_ids)
    assigned = service.current_user.branch_id
    if assigned in branch_options:
        branch_options.remove(assigned)
        branch_options.insert(0, assigned)
    rows: list[ManualOverrideRow] = [
        dict(row) for row in st.session_state.get("manual_override_rows", [])
    ]
    groups: list[dict[str, str]] = [
        dict(group) for group in st.session_state.get("manual_override_groups", [])
    ]
    known_group_ids = {group["group_id"] for group in groups}
    for row in rows:
        if row["group_id"] not in known_group_ids:
            groups.append({"group_id": row["group_id"], "branch_id": row["branch_id"]})
            known_group_ids.add(row["group_id"])

    add_columns = st.columns([2, 1, 3])
    with add_columns[0]:
        new_branch = st.selectbox(
            "شعبه دارای استثنا",
            branch_options,
            format_func=lambda item: f"{names.get(item, item)} ({item})",
            key="override_new_branch",
        )
    with add_columns[1]:
        st.write("")
        if st.button("افزودن استثنای شعبه", key="override_add_group"):
            if any(group["branch_id"] == new_branch for group in groups):
                st.warning("برای این شعبه قبلاً گروه استثنا ایجاد شده است.")
            else:
                groups.append({"group_id": str(uuid4()), "branch_id": new_branch})
                st.session_state["manual_override_groups"] = groups
                st.rerun()

    for group in list(groups):
        group_id = group["group_id"]
        branch_id = group["branch_id"]
        group_rows = [row for row in rows if row["group_id"] == group_id]
        existing = {row["indicator_key"]: row for row in group_rows}
        with st.expander(
            f"{names.get(branch_id, branch_id)} ({branch_id}) — "
            f"تعداد شاخص‌های تغییر یافته: {len(group_rows)} — ویرایش",
            expanded=not group_rows,
        ):
            st.markdown("##### تنظیم شاخص‌های شعبه")
            with st.form(f"override_group_form_{group_id}"):
                for indicator_key, indicator in INDICATOR_REGISTRY.items():
                    current = existing.get(indicator_key)
                    if current:
                        label, displayed = domain_rule_to_ui(
                            RuleOperation(current["operation"]),
                            float(current["input_value"]),
                        )
                    else:
                        label, displayed = NO_CHANGE_LABEL, 0.0
                    operation_key = f"exception_{branch_id}_{indicator_key}_operation"
                    value_key = f"exception_{branch_id}_{indicator_key}_value"
                    value_disabled = _prepare_rule_widgets(
                        operation_key=operation_key,
                        value_key=value_key,
                        default_label=label,
                        default_value=displayed,
                    )
                    columns = st.columns([2, 1.5, 1])
                    with columns[0]:
                        st.write(indicator.display_name)
                    with columns[1]:
                        option = st.selectbox(
                            f"عملیات {indicator.display_name}", RULE_UI_OPTIONS,
                            key=operation_key, label_visibility="collapsed",
                        )
                    with columns[2]:
                        st.number_input(
                            f"مقدار {indicator.display_name}", value=0.0,
                            key=value_key,
                            disabled=value_disabled,
                            label_visibility="collapsed",
                        )
                submitted_group = st.form_submit_button("ثبت استثناهای این شعبه")
            actions = st.columns([1, 1, 4])
            with actions[0]:
                st.caption("برای ویرایش، مقادیر بالا را تغییر دهید و ثبت کنید.")
            with actions[1]:
                delete_group = st.button("حذف", key=f"override_delete_group_{group_id}")
            if delete_group:
                rows = delete_override_group(rows, group_id)
                groups = [item for item in groups if item["group_id"] != group_id]
                st.session_state["manual_override_rows"] = rows
                st.session_state["manual_override_groups"] = groups
                st.rerun()
            if submitted_group:
                replacement: list[ManualOverrideRow] = []
                for indicator_key in INDICATOR_REGISTRY:
                    option = st.session_state[f"exception_{branch_id}_{indicator_key}_operation"]
                    value = float(st.session_state[f"exception_{branch_id}_{indicator_key}_value"])
                    converted = ui_rule_to_domain(option, value)
                    if converted is None:
                        continue
                    previous = existing.get(indicator_key)
                    replacement.append(
                        new_override_row(
                            branch_id=branch_id,
                            indicator_key=indicator_key,
                            operation=converted[0],
                            input_value=converted[1],
                            group_id=group_id,
                            source="branch_exception",
                            row_id_factory=(
                                (lambda row_id=previous["row_id"]: row_id)
                                if previous else (lambda: str(uuid4()))
                            ),
                        )
                    )
                rows = replace_override_group(rows, group_id, replacement)
                st.session_state["manual_override_rows"] = rows
                if replacement:
                    st.success("استثناهای این شعبه ثبت شد.")
                else:
                    st.info("برای این شعبه تغییری ثبت نشده است.")

    st.session_state["manual_override_rows"] = rows
    st.session_state["manual_override_groups"] = groups
    duplicates = duplicate_override_keys(rows)
    if duplicates:
        st.error("برای این شعبه و شاخص قبلاً استثنا ثبت شده است.")
    branch_exception_groups = {
        group["branch_id"]: {
            row["indicator_key"]: {
                "operation": row["operation"],
                "input_value": row["input_value"],
            }
            for row in rows if row["group_id"] == group["group_id"]
        }
        for group in groups
    }
    st.session_state["branch_exception_groups"] = branch_exception_groups
    overrides = to_domain_overrides(rows, default_source="branch_exception")
    user_preview = ScenarioRuleEngine.preview(
        [user_branch_id], baseline_df, [],
        to_domain_overrides(user_rows, default_source="focus_branch_override")
    )
    network_preview = ScenarioRuleEngine.preview(other_ids, baseline_df, rules, overrides)
    preview = RulePreview(
        selected_branch_count=1 + len(other_ids),
        active_bulk_rule_count=network_preview.active_bulk_rule_count,
        unchanged_indicator_count=network_preview.unchanged_indicator_count,
        manual_override_count=(
            user_preview.manual_override_count + network_preview.manual_override_count
        ),
        generated_change_count=(
            user_preview.generated_change_count + network_preview.generated_change_count
        ),
        invalid_change_count=(
            user_preview.invalid_change_count + network_preview.invalid_change_count
        ),
        rows=[*user_preview.rows, *network_preview.rows],
        changes=[*user_preview.changes, *network_preview.changes],
        issues=[*user_preview.issues, *network_preview.issues],
    )
    selected_ids = [user_branch_id, *other_ids]
    definition = {
        "schema_version": 2,
        "scenario_mode": st.session_state["scenario_mode"],
        "focus_branch_id": user_branch_id,
        "focus_branch_source": st.session_state["focus_branch_source"],
        "selection_scope": st.session_state["selection_scope"],
        "selection_inputs": {
            "selected_regions": list(st.session_state["selected_regions"]),
            "selected_branch_ids": list(selected_ids),
        },
        "bulk_rules": ScenarioRuleEngine.serialize_rules(rules),
        "network_bulk_rules": ScenarioRuleEngine.serialize_rules(rules),
        "focus_branch_overrides": serialize_override_rows(user_rows),
        "manual_overrides": serialize_override_rows(rows),
        "branch_exception_groups": branch_exception_groups,
        "validation_status": "valid" if preview.is_valid else "invalid",
    }
    focus_changed_count = sum(
        row.change_source == "focus_branch_override" for row in user_preview.rows
    )
    exception_changed_count = sum(
        row.change_source == "branch_exception" for row in network_preview.rows
    )
    metrics = st.columns(6)
    values = (
        ("تغییرات شعبه محوری", focus_changed_count),
        ("شعب استثنا", sum(bool(items) for items in branch_exception_groups.values())),
        ("شاخص‌های استثنا", exception_changed_count),
        ("قوانین فعال شبکه", preview.active_bulk_rule_count),
        ("تغییرات تولیدشده", preview.generated_change_count),
        ("خطاها", preview.invalid_change_count),
    )
    for column, (label, value) in zip(metrics, values):
        with column:
            st.metric(label, value)
    show_all = st.checkbox("نمایش ردیف‌های بدون تغییر", value=False)
    user_df = pd.DataFrame([row.__dict__ for row in user_preview.rows])
    network_df = pd.DataFrame([row.__dict__ for row in network_preview.rows])
    if not show_all:
        if not user_df.empty:
            user_df = user_df.loc[
                user_df["final_value"].ne(user_df["baseline_value"])
                | user_df["validation_status"].eq("invalid")
            ]
        if not network_df.empty:
            network_df = network_df.loc[
                network_df["final_value"].ne(network_df["baseline_value"])
                | network_df["validation_status"].eq("invalid")
            ]
    source_labels = {
        "baseline": "baseline",
        "bulk_rule": "network_bulk_rule",
        "manual_override": "branch_exception",
    }
    if not user_df.empty:
        user_df["change_source"] = user_df["change_source"].replace(
            {"manual_override": "focus_branch_override"}
        )
    if not network_df.empty:
        network_df["change_source"] = network_df["change_source"].replace(source_labels)
    st.markdown(
        "#### تغییرات شعبه من"
        if st.session_state.get("focus_branch_source") == "ASSIGNED_USER_BRANCH"
        else "#### تغییرات شعبه محوری تحلیل"
    )
    if user_df.empty:
        st.caption("تغییری ثبت نشده است.")
    else:
        st.dataframe(user_df, width="stretch", height=280)
    st.markdown("#### تغییرات قاعده عمومی شبکه")
    bulk_df = network_df.loc[network_df["change_source"].eq("network_bulk_rule")] if not network_df.empty else network_df
    if bulk_df.empty:
        st.caption("تغییری ثبت نشده است.")
    else:
        st.dataframe(bulk_df, width="stretch", height=280)
    st.markdown("#### استثناهای شعب")
    exception_df = network_df.loc[network_df["change_source"].eq("branch_exception")] if not network_df.empty else network_df
    if exception_df.empty:
        st.caption("استثنایی ثبت نشده است.")
    else:
        st.dataframe(exception_df, width="stretch", height=280)
    if preview.issues:
        st.error(
            f"{preview.invalid_change_count} تغییر در {preview.invalid_branch_count} شعبه "
            "نامعتبر است و اجرای سناریو مسدود شده است."
        )
        with st.expander("جزئیات خطاهای اعتبارسنجی"):
            st.dataframe(pd.DataFrame([issue.__dict__ for issue in preview.issues]), width="stretch")
    return preview, definition


@st.cache_data(show_spinner="در حال بارگذاری و محاسبه اطلاعات مبنا...")
def load_baseline_data(data_file: Path) -> tuple[pd.DataFrame, ModelOutputs]:
    """Load repository data and cache its single baseline-model calculation."""
    return load_dashboard_data(data_file, MODEL_PERIOD)


@st.cache_resource
def get_scenario_service(project_root: Path) -> ScenarioManagementService:
    """Create the local persistence service without retaining a DB connection."""
    return create_local_scenario_service(project_root)


def reset_scenario() -> None:
    """Streamlit callback for a local scenario reset."""
    reset_scenario_state(st.session_state)


def _settings(
    baseline_df: pd.DataFrame, service: ScenarioManagementService
) -> tuple[str, str | None, list[str], list[str]]:
    """Render top-of-page scenario settings."""
    if "_scenario_name_input" not in st.session_state:
        st.session_state["_scenario_name_input"] = st.session_state["scenario_name"]
    name_column, period_column, reset_column = st.columns([2.5, 1, 1])
    with name_column:
        scenario_name = st.text_input(
            "نام سناریو",
            key="_scenario_name_input",
            placeholder="برای مثال: رشد ۱۰ درصدی سپرده‌ها",
        )
    with period_column:
        st.selectbox("دوره انتخابی", options=[MODEL_PERIOD], disabled=True)
    with reset_column:
        st.write("")
        st.write("")
        st.button("بازنشانی", width="stretch", on_click=reset_scenario)

    user = service.current_user
    all_ids = baseline_df[BRANCH_ID].astype(str).tolist()
    names = baseline_df.assign(**{BRANCH_ID: baseline_df[BRANCH_ID].astype(str)}).set_index(
        BRANCH_ID
    )[BRANCH_NAME].to_dict()
    persisted_focus = (
        st.session_state.get("focus_branch_id")
        if st.session_state.get("current_scenario_record") is not None
        else None
    )
    persisted_source = (
        st.session_state.get("focus_branch_source") if persisted_focus else None
    )
    staff_selection = None
    if not user.branch_id and not persisted_focus:
        staff_selection = st.selectbox(
            "شعبه محوری تحلیل",
            options=[None, *all_ids],
            format_func=lambda branch_id: (
                "انتخاب شعبه" if branch_id is None
                else f"{names[branch_id]} ({branch_id})"
            ),
            key="_focus_branch_input",
        )
    try:
        focus = resolve_focus_branch(
            user,
            baseline_df,
            selected_branch_id=staff_selection,
            persisted_branch_id=persisted_focus,
            persisted_source=persisted_source,
        )
    except ValueError as exc:
        st.warning(str(exc))
        return scenario_name, None, [], []
    if focus is None:
        st.info("برای شروع، شعبه محوری تحلیل را انتخاب کنید.")
        return scenario_name, None, [], []
    focus_branch_id = focus.branch_id
    st.session_state["focus_branch_id"] = focus.branch_id
    st.session_state["focus_branch_source"] = focus.source.value
    focus_label = "شعبه من" if user.branch_id else "شعبه محوری تحلیل"
    st.caption(
        f"{focus_label}: {names[focus_branch_id]} — "
        f"کد {(user.branch_code or focus_branch_id) if user.branch_id else focus_branch_id}"
    )
    mode_labels = scenario_mode_labels(user)
    mode = st.radio(
        "رفتار سایر شعب در سناریو چگونه باشد؟",
        options=list(mode_labels),
        format_func=mode_labels.get,
        horizontal=True,
        key="_scenario_mode_input",
    )
    st.session_state["scenario_mode"] = mode
    if mode == "ONLY_USER_BRANCH":
        st.session_state["selection_scope"] = SelectionScope.USER_BRANCH.value
        st.session_state["selected_regions"] = []
        st.session_state["selected_branch_ids"] = [focus_branch_id]
        return scenario_name, focus_branch_id, [], [focus_branch_id]

    st.markdown("#### دامنه تغییر سایر شعب")
    scope = st.radio(
        "دامنه تغییر سایر شعب",
        options=list(OTHER_SCOPE_LABELS),
        format_func=OTHER_SCOPE_LABELS.get,
        horizontal=True,
        key="_other_selection_scope_input",
        label_visibility="collapsed",
    )
    st.session_state["selection_scope"] = scope.value

    if scope is SelectionScope.SELECTED_BRANCHES:
        current = st.session_state.get(
            "_selected_branch_ids_input", st.session_state["selected_branch_ids"]
        )
        st.session_state["_selected_branch_ids_input"] = [
            item for item in current if item in set(all_ids) and item != focus_branch_id
        ]
        manual_ids = st.multiselect(
            "انتخاب شعب",
            options=[item for item in all_ids if item != focus_branch_id],
            format_func=lambda branch_id: f"{names[branch_id]} ({branch_id})",
            key="_selected_branch_ids_input",
            placeholder="نام یا کد شعبه را جست‌وجو کنید",
        )
        selected_regions: list[str] = []
    elif scope is SelectionScope.SELECTED_REGIONS:
        region_options = sorted(baseline_df[REGION].astype(str).unique().tolist())
        selected_regions = st.multiselect(
            "انتخاب مناطق",
            options=region_options,
            key="_selected_regions_input",
        )
        manual_ids = []
    elif scope is SelectionScope.ALL_BRANCHES:
        selected_regions = []
        manual_ids = []

    try:
        other_ids = SelectionResolver.resolve(
            scope,
            baseline_df,
            service.current_user,
            selected_branch_ids=manual_ids,
            selected_regions=selected_regions,
        )
    except SelectionResolutionError as exc:
        st.info(str(exc))
        other_ids = []

    other_ids = [item for item in other_ids if item != focus_branch_id]
    selected_ids = [focus_branch_id, *other_ids]

    st.session_state["selected_regions"] = list(selected_regions)
    st.session_state["selected_branch_ids"] = list(selected_ids)
    summary = f"تعداد سایر شعب: {len(other_ids)} | مجموع شعب تحت تغییر: {len(selected_ids)}"
    if scope is SelectionScope.SELECTED_REGIONS:
        summary += f" | تعداد مناطق منتخب: {len(selected_regions)}"
    st.caption(summary)
    return scenario_name, focus_branch_id, other_ids, selected_ids


def render_persistence_status(service: ScenarioManagementService) -> None:
    """Show owner, status, last update, and technical persistence identity."""
    record: ScenarioRecord | None = st.session_state["current_scenario_record"]
    owner = record.owner_display_name if record else service.current_user.display_name
    status_labels = {"draft": "پیش‌نویس", "executed": "اجراشده", "archived": "بایگانی‌شده"}
    columns = st.columns(3)
    with columns[0]:
        st.caption(f"مالک: {owner}")
    with columns[1]:
        st.caption(f"وضعیت: {status_labels.get(record.status, 'ذخیره‌نشده') if record else 'ذخیره‌نشده'}")
    with columns[2]:
        updated = record.updated_at.astimezone().strftime("%Y-%m-%d %H:%M") if record else "—"
        st.caption(f"آخرین ویرایش: {updated}")
    if record is not None:
        with st.expander("اطلاعات فنی سناریو"):
            st.code(
                f"scenario_id: {record.scenario_id}\nrow_version: {record.row_version}",
                language=None,
            )


def render_baseline_summary(
    final_result: pd.DataFrame, selected_branch_ids: list[str]
) -> None:
    """Render single-branch KPIs or a multi-branch baseline table."""
    selected = final_result.loc[
        final_result[BRANCH_ID].isin(selected_branch_ids),
        [BRANCH_ID, BRANCH_NAME, REGION, "final_score", "rank", "grade"],
    ].copy()
    order = {branch_id: position for position, branch_id in enumerate(selected_branch_ids)}
    selected["_order"] = selected[BRANCH_ID].map(order)
    selected = selected.sort_values("_order").drop(columns="_order")
    st.subheader("وضعیت مبنای شعب منتخب")
    def render_branch(row: pd.Series) -> None:
        groups = st.columns(2)
        with groups[0]:
            render_kpi_group(
                "مشخصات شعبه",
                (
                    ("نام شعبه", row[BRANCH_NAME], None, "off"),
                    ("کد شعبه", row[BRANCH_ID], None, "off"),
                    ("منطقه", row[REGION], None, "off"),
                ),
            )
        with groups[1]:
            render_kpi_group(
                "وضعیت مبنا",
                (
                    ("امتیاز", format_score(row["final_score"]), None, "off"),
                    ("رتبه", format_rank(row["rank"]), None, "off"),
                    ("درجه", format_grade(row["grade"]), None, "off"),
                ),
            )

    if len(selected) == 1:
        render_branch(selected.iloc[0])
        return
    selected["final_score"] = selected["final_score"].map(format_score)
    selected["rank"] = selected["rank"].map(format_rank)
    selected["grade"] = selected["grade"].map(format_grade)
    render_table(
        selected.rename(
            columns={
                BRANCH_ID: "کد شعبه",
                BRANCH_NAME: "نام شعبه",
                REGION: "منطقه",
                "final_score": "امتیاز مبنا",
                "rank": "رتبه مبنا",
                "grade": "درجه مبنا",
            }
        ),
        height=min(360, 52 + len(selected) * 36),
        column_config={
            "کد شعبه": st.column_config.TextColumn(width="small"),
            "نام شعبه": st.column_config.TextColumn(width="medium"),
            "منطقه": st.column_config.TextColumn(width="medium"),
            "امتیاز مبنا": st.column_config.TextColumn(width="small"),
            "رتبه مبنا": st.column_config.TextColumn(width="small"),
            "درجه مبنا": st.column_config.TextColumn(width="small"),
        },
    )


def _write_row_widget_state(row: dict[str, object]) -> None:
    """Synchronize one reset row with its three stable Streamlit widget keys."""
    branch_id = str(row[BRANCH_ID])
    indicator_key = str(row["indicator_key"])
    st.session_state[indicator_widget_key(branch_id, indicator_key, "edit_mode")] = row[
        "edit_mode"
    ]
    st.session_state[
        indicator_widget_key(branch_id, indicator_key, "change_percent")
    ] = row["change_percent"]
    st.session_state[
        indicator_widget_key(branch_id, indicator_key, "scenario_value")
    ] = row["scenario_value"]


def _reset_editor_row(branch_id: str, indicator_key: str) -> None:
    state = reset_indicator_row(
        st.session_state["indicator_editor_state"], branch_id, indicator_key
    )
    st.session_state["indicator_editor_state"] = state
    _write_row_widget_state(state[f"{branch_id}:{indicator_key}"])


def _reset_editor_all() -> None:
    state = reset_all_indicator_rows(st.session_state["indicator_editor_state"])
    st.session_state["indicator_editor_state"] = state
    for row in state.values():
        _write_row_widget_state(row)


def _clear_editor_widget_state() -> None:
    suffixes = ("_edit_mode", "_change_percent", "_scenario_value")
    for key in list(st.session_state):
        if key.startswith("scenario_") and key.endswith(suffixes):
            st.session_state.pop(key, None)


def render_scenario_editor(
    editor_state: dict[str, dict[str, object]], *, can_update: bool = True
) -> tuple[dict[str, dict[str, object]], bool, bool]:
    """Render explicit row controls with one authoritative input per indicator."""
    heading, reset_column = st.columns([5, 1])
    with heading:
        st.subheader("ویرایش شاخص‌های سناریو")
        st.caption(
            "برای هر شاخص روش درصدی یا ورود مستقیم را انتخاب کنید. مقدار غیرفعال "
            "به‌صورت خودکار محاسبه می‌شود."
        )
    with reset_column:
        st.write("")
        st.button(
            "بازنشانی همه شاخص‌ها",
            key="_reset_all_indicators",
            on_click=_reset_editor_all,
            width="stretch",
        )

    branch_ids = list(dict.fromkeys(str(row[BRANCH_ID]) for row in editor_state.values()))
    branch_names = {
        str(row[BRANCH_ID]): str(row[BRANCH_NAME]) for row in editor_state.values()
    }
    tabs = (
        st.tabs([f"{branch_names[item]} ({item})" for item in branch_ids])
        if len(branch_ids) > 1
        else [st.container()]
    )
    current = {key: dict(value) for key, value in editor_state.items()}
    for tab, branch_id in zip(tabs, branch_ids):
        with tab:
            headers = st.columns([2.2, 1.5, 1.35, 1.45, 1.65, 1.35, 0.75])
            for column, label in zip(
                headers,
                ("شاخص", "مقدار مبنا", "روش ویرایش", "درصد تغییر", "مقدار سناریو", "تغییر عددی", ""),
            ):
                column.caption(label)
            for indicator_key in INDICATOR_ORDER:
                row_id = f"{branch_id}:{indicator_key}"
                row = current[row_id]
                baseline = float(row["baseline_value"])
                mode_key = indicator_widget_key(branch_id, indicator_key, "edit_mode")
                percent_key = indicator_widget_key(
                    branch_id, indicator_key, "change_percent"
                )
                value_key = indicator_widget_key(
                    branch_id, indicator_key, "scenario_value"
                )
                st.session_state.setdefault(mode_key, str(row["edit_mode"]))
                st.session_state.setdefault(percent_key, row["change_percent"])
                st.session_state.setdefault(value_key, float(row["scenario_value"]))

                columns = st.columns([2.2, 1.5, 1.35, 1.45, 1.65, 1.35, 0.75])
                columns[0].write(str(row["indicator_name"]))
                columns[1].write(format_raw_value(baseline))
                with columns[2]:
                    mode = st.selectbox(
                        "روش ویرایش",
                        options=["percent", "direct"],
                        format_func=lambda item: "درصدی" if item == "percent" else "مقداری",
                        key=mode_key,
                        label_visibility="collapsed",
                    )

                if mode == "percent":
                    if not isinstance(st.session_state.get(percent_key), (int, float)):
                        st.session_state[percent_key] = 0.0
                    with columns[3]:
                        percent = st.number_input(
                            "درصد تغییر",
                            key=percent_key,
                            format="%.2f",
                            label_visibility="collapsed",
                        )
                    scenario_value = calculate_scenario_value(baseline, float(percent))
                    st.session_state[value_key] = scenario_value
                    with columns[4]:
                        st.number_input(
                            "مقدار سناریو",
                            key=value_key,
                            disabled=True,
                            format="%.2f",
                            label_visibility="collapsed",
                        )
                else:
                    if not isinstance(st.session_state.get(value_key), (int, float)):
                        st.session_state[value_key] = baseline
                    with columns[4]:
                        scenario_value = st.number_input(
                            "مقدار سناریو",
                            key=value_key,
                            format="%.2f",
                            label_visibility="collapsed",
                        )
                    percent = calculate_change_percent(baseline, float(scenario_value))
                    st.session_state[percent_key] = percent if percent is not None else "—"
                    with columns[3]:
                        if percent is None:
                            st.text_input(
                                "درصد تغییر",
                                key=percent_key,
                                disabled=True,
                                label_visibility="collapsed",
                            )
                        else:
                            st.number_input(
                                "درصد تغییر",
                                key=percent_key,
                                disabled=True,
                                format="%.2f",
                                label_visibility="collapsed",
                            )

                absolute_change = float(scenario_value) - baseline
                color = "#16794f" if absolute_change > 0 else "#b42318" if absolute_change < 0 else "inherit"
                sign = "+" if absolute_change > 0 else ""
                columns[5].markdown(
                    f"<span style='color:{color};font-weight:600'>{sign}{format_raw_value(absolute_change)}</span>",
                    unsafe_allow_html=True,
                )
                with columns[6]:
                    st.button(
                        "↺",
                        key=indicator_widget_key(branch_id, indicator_key, "reset"),
                        help="بازنشانی این شاخص",
                        on_click=_reset_editor_row,
                        args=(branch_id, indicator_key),
                    )
                if baseline == 0 and mode == "percent":
                    st.caption(
                        "برای مقدار مبنای صفر، ورود درصدی اثری ندارد؛ مقدار سناریو را مستقیم وارد کنید."
                    )
                row.update(
                    edit_mode=mode,
                    change_percent=percent,
                    scenario_value=float(scenario_value),
                    absolute_change=absolute_change,
                )

    synchronized = update_indicator_editor_state(current)
    st.session_state["indicator_editor_state"] = synchronized
    actions = st.columns([1, 1, 3])
    with actions[0]:
        submitted = st.button("اجرای سناریو", type="primary", width="content")
    with actions[1]:
        save_draft = st.button(
            "ذخیره پیش‌نویس", width="content", disabled=not can_update
        )
    return synchronized, submitted, save_draft


def _store_saved_record(record: ScenarioRecord) -> None:
    """Update the three persistence identity keys after a successful save."""
    st.session_state["current_scenario_id"] = record.scenario_id
    st.session_state["current_scenario_row_version"] = record.row_version
    st.session_state["current_scenario_dirty"] = False
    st.session_state["current_scenario_record"] = record


def _save_draft(
    service: ScenarioManagementService,
    changes: list,
    definition: dict[str, object],
    scenario_name: str,
    selected_ids: list[str],
) -> None:
    record = service.save_draft(
        scenario_name=scenario_name,
        baseline_period=MODEL_PERIOD,
        selected_branch_ids=selected_ids,
        changes=changes,
        summary={"scenario_definition": definition},
        scenario_id=st.session_state["current_scenario_id"],
        expected_row_version=st.session_state["current_scenario_row_version"],
    )
    _store_saved_record(record)
    st.session_state.update(
        {
            "scenario_name": scenario_name.strip(),
            "selected_branch_ids": list(selected_ids),
            "scenario_changes": changes,
            "scenario_dataframe": None,
            "scenario_outputs": None,
            "comparison_results": None,
            "scenario_executed": False,
            "scenario_definition": definition,
            "loaded_scenario_changes": changes,
            "loaded_scenario_edit_modes": {},
        }
    )


def _save_executed(
    service: ScenarioManagementService,
    *,
    save_as_new: bool,
) -> ScenarioRecord:
    record = service.save_executed(
        scenario_name=st.session_state["scenario_name"],
        baseline_period=MODEL_PERIOD,
        selected_branch_ids=st.session_state["selected_branch_ids"],
        changes=st.session_state["scenario_changes"],
        comparison=st.session_state["comparison_results"],
        summary={"scenario_definition": st.session_state["scenario_definition"]},
        scenario_id=st.session_state["current_scenario_id"],
        expected_row_version=st.session_state["current_scenario_row_version"],
        save_as_new=save_as_new,
    )
    _store_saved_record(record)
    return record


def _show_persistence_error(exc: Exception) -> None:
    if isinstance(exc, ConcurrencyError):
        st.error(
            "این سناریو در نشست دیگری تغییر کرده است. صفحه سناریوهای ذخیره‌شده را "
            "بازخوانی کنید و دوباره تلاش کنید."
        )
    elif isinstance(exc, (ValueError, ScenarioPersistenceError)):
        st.error(str(exc))
    else:
        st.error("ذخیره سناریو انجام نشد. لطفاً دوباره تلاش کنید.")


def _change_delta(value: float, formatter) -> tuple[str | None, str]:
    """Return a native metric delta and its neutral/color mode."""
    if value == 0:
        return "بدون تغییر", "off"
    return formatter(value), "normal"


def _render_branch_kpis(row: pd.Series) -> None:
    score_delta, score_color = _change_delta(float(row["score_change"]), format_score)
    rank_delta, rank_color = _change_delta(float(row["rank_change"]), format_rank_change)
    if float(row["rank_change"]) < 0:
        rank_color = "inverse"
    groups = st.columns(3)
    with groups[0]:
        render_kpi_group(
            "امتیاز",
            (
                ("مبنا", format_score(row["baseline_score"]), None, "off"),
                ("سناریو", format_score(row["scenario_score"]), None, "off"),
                ("تغییر", format_score(row["score_change"]), score_delta, score_color),
            ),
        )
    with groups[1]:
        render_kpi_group(
            "رتبه",
            (
                ("مبنا", format_rank(row["baseline_rank"]), None, "off"),
                ("سناریو", format_rank(row["scenario_rank"]), None, "off"),
                ("تغییر", format_rank_change(row["rank_change"]), rank_delta, rank_color),
            ),
        )
    with groups[2]:
        render_kpi_group(
            "درجه",
            (
                ("مبنا", format_grade(row["baseline_grade"]), None, "off"),
                ("سناریو", format_grade(row["scenario_grade"]), None, "off"),
            ),
        )


def _indicator_tables(indicators: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    result = indicators.copy()
    order = {key: index for index, key in enumerate(INDICATOR_ORDER)}
    result["_order"] = result["indicator_key"].map(order)
    result = result.sort_values("_order")
    result["indicator_key"] = result["indicator_key"].map(INDICATOR_LABELS)
    values = result.loc[
        :,
        [
            "indicator_key",
            "baseline_raw_value",
            "scenario_raw_value",
            "raw_value_change",
            "raw_value_change_pct",
        ],
    ].rename(
        columns={
            "indicator_key": "شاخص",
            "baseline_raw_value": "مقدار مبنا",
            "scenario_raw_value": "مقدار سناریو",
            "raw_value_change": "تغییر",
            "raw_value_change_pct": "درصد تغییر",
        }
    )
    values["مقدار مبنا"] = values["مقدار مبنا"].map(format_raw_value)
    values["مقدار سناریو"] = values["مقدار سناریو"].map(format_raw_value)
    values["تغییر"] = values["تغییر"].map(format_raw_value)
    values["درصد تغییر"] = values["درصد تغییر"].map(
        lambda value: format_percentage(value, decimals=2)
    )
    scores = result.loc[
        :,
        [
            "indicator_key",
            "baseline_score",
            "scenario_score",
            "baseline_weighted_score",
            "scenario_weighted_score",
            "baseline_indicator_rank",
            "scenario_indicator_rank",
            "indicator_rank_change",
        ],
    ].rename(
        columns={
            "indicator_key": "شاخص",
            "baseline_score": "امتیاز نرمال‌شده مبنا",
            "scenario_score": "امتیاز نرمال‌شده سناریو",
            "baseline_weighted_score": "امتیاز وزن‌دار مبنا",
            "scenario_weighted_score": "امتیاز وزن‌دار سناریو",
            "baseline_indicator_rank": "رتبه مبنا",
            "scenario_indicator_rank": "رتبه سناریو",
            "indicator_rank_change": "تغییر رتبه",
        }
    )
    for column in (
        "امتیاز نرمال‌شده مبنا",
        "امتیاز نرمال‌شده سناریو",
        "امتیاز وزن‌دار مبنا",
        "امتیاز وزن‌دار سناریو",
    ):
        scores[column] = scores[column].map(format_score)
    scores["رتبه مبنا"] = scores["رتبه مبنا"].map(format_rank)
    scores["رتبه سناریو"] = scores["رتبه سناریو"].map(format_rank)
    scores["تغییر رتبه"] = scores["تغییر رتبه"].map(format_rank_change)
    return values, scores


def _render_indicator_charts(
    indicator_comparison: pd.DataFrame,
    indicators: pd.DataFrame,
    selected_branch_id: str,
) -> None:
    score_data = prepare_selected_indicator_scores(
        indicator_comparison, selected_branch_id
    )
    validate_indicator_score_chart_matches_table(score_data, indicators)
    score_figure = build_selected_indicator_score_chart(score_data)
    render_chart(
        score_figure, key=f"selected_branch_indicator_comparison_{selected_branch_id}"
    )

    chart_data = indicators.copy()
    order = {key: index for index, key in enumerate(INDICATOR_ORDER)}
    chart_data["_order"] = chart_data["indicator_key"].map(order)
    chart_data = chart_data.sort_values("_order")
    labels = chart_data["indicator_key"].map(INDICATOR_LABELS)
    rank_figure = build_indicator_rank_lollipop(
        labels,
        chart_data["indicator_rank_change"],
    )
    render_chart(
        rank_figure, key=f"selected_branch_indicator_rank_{selected_branch_id}"
    )


def _select_result_branch(branch_id: str) -> None:
    st.session_state["_selected_result_branch_id"] = branch_id


def render_selected_branch_results(
    comparison, selected_ids: list[str], preferred_branch_id: str | None = None
) -> None:
    """Render one searchable, ordered selected-branch result at a time."""
    branches = selected_branch_results(comparison, selected_ids)
    region_options = sorted(branches[REGION].astype(str).unique().tolist())
    grade_options = sorted(branches["scenario_grade"].astype(str).unique().tolist())
    filters = st.columns(2)
    with filters[0]:
        region_filter = st.selectbox(
            "فیلتر منطقه", [None, *region_options],
            format_func=lambda item: "همه مناطق" if item is None else item,
            key="_result_region_filter",
        )
    with filters[1]:
        grade_filter = st.selectbox(
            "فیلتر درجه", [None, *grade_options],
            format_func=lambda item: "همه درجات" if item is None else format_grade(item),
            key="_result_grade_filter",
        )
    filtered = branches
    if region_filter is not None:
        filtered = filtered.loc[filtered[REGION].eq(region_filter)]
    if grade_filter is not None:
        filtered = filtered.loc[filtered["scenario_grade"].eq(grade_filter)]
    ordered_ids = filtered[BRANCH_ID].astype(str).tolist()
    if not ordered_ids:
        render_empty_state("شعبه‌ای مطابق فیلترهای انتخاب‌شده وجود ندارد.")
        return
    current = retain_selected_branch(
        ordered_ids,
        st.session_state.get("_selected_result_branch_id") or preferred_branch_id,
    )
    assert current is not None
    st.session_state["_selected_result_branch_id"] = current
    labels = filtered.set_index(BRANCH_ID)[BRANCH_NAME].to_dict()
    selected_id = st.selectbox(
        "جست‌وجو و انتخاب شعبه",
        ordered_ids,
        format_func=lambda item: f"{labels[item]} ({item})",
        key="_selected_result_branch_id",
    )
    position = ordered_ids.index(selected_id)
    navigation = st.columns([1, 1, 3])
    with navigation[0]:
        st.button(
            "شعبه قبلی", on_click=_select_result_branch,
            args=(adjacent_branch_id(ordered_ids, selected_id, step=-1),),
            width="stretch",
        )
    with navigation[1]:
        st.button(
            "شعبه بعدی", on_click=_select_result_branch,
            args=(adjacent_branch_id(ordered_ids, selected_id, step=1),),
            width="stretch",
        )
    with navigation[2]:
        st.caption(f"شعبه {position + 1} از {len(ordered_ids)}")
    branch = filtered.loc[filtered[BRANCH_ID].astype(str).eq(selected_id)].iloc[0]
    st.markdown(f"### {branch[BRANCH_NAME]} — کد {branch[BRANCH_ID]}")
    st.caption(f"منطقه: {branch[REGION]} | درجه سناریو: {format_grade(branch['scenario_grade'])}")
    _render_branch_kpis(branch)
    network = comparison.branch_comparison
    region_rows = network.loc[network[REGION].eq(branch[REGION])].copy()
    region_rows["scenario_region_rank"] = region_rows["scenario_score"].rank(
        method="min", ascending=False
    ).astype(int)
    region_rank = int(
        region_rows.loc[
            region_rows[BRANCH_ID].astype(str).eq(selected_id), "scenario_region_rank"
        ].iloc[0]
    )
    better = network.loc[network["scenario_rank"].lt(branch["scenario_rank"])]
    next_better_gap = (
        float(better.sort_values("scenario_rank", ascending=False).iloc[0]["scenario_score"])
        - float(branch["scenario_score"])
        if not better.empty else 0.0
    )
    overtaken = network.loc[
        network["baseline_rank"].lt(branch["baseline_rank"])
        & network["scenario_rank"].gt(branch["scenario_rank"])
    ]
    overtook_user = network.loc[
        network["baseline_rank"].gt(branch["baseline_rank"])
        & network["scenario_rank"].lt(branch["scenario_rank"])
    ]
    st.markdown("#### جایگاه در شبکه")
    context_columns = st.columns(3)
    context_values = (
        ("رتبه در کل بانک", format_rank(branch["scenario_rank"])),
        ("رتبه در منطقه", format_rank(region_rank)),
        ("فاصله تا رتبه بهتر", format_score(next_better_gap)),
        (
            "فاصله تا میانگین شبکه",
            format_score(float(branch["scenario_score"]) - float(network["scenario_score"].mean())),
        ),
        ("شعب پشت سر گذاشته‌شده", format_number(len(overtaken))),
        ("شعب عبورکرده از شعبه من", format_number(len(overtook_user))),
        (
            "کل شعب دارای تغییر رتبه",
            format_number(int(network["rank_change"].ne(0).sum())),
        ),
    )
    for index, (label, value) in enumerate(context_values):
        with context_columns[index % 3]:
            st.metric(label, value)
    indicators = comparison.indicator_comparison.loc[
        comparison.indicator_comparison[BRANCH_ID].astype(str).eq(selected_id)
    ].copy()
    st.subheader("مقایسه شاخص‌ها")
    values, scores = _indicator_tables(indicators)
    value_tab, score_tab = st.tabs(["مقادیر خام شاخص‌ها", "امتیاز نرمال و رتبه شاخص‌ها"])
    with value_tab:
        render_indicator_values_table(values)
    with score_tab:
        render_indicator_scores_table(scores)
    drivers = indicators.loc[indicators["weighted_score_change"].ne(0)].copy()
    if not drivers.empty:
        drivers["indicator_name"] = drivers["indicator_key"].map(INDICATOR_LABELS)
        drivers = drivers.sort_values(
            "weighted_score_change", key=lambda series: series.abs(), ascending=False
        ).head(5)
        st.markdown("#### عوامل اصلی بهبود یا افت")
        st.dataframe(
            drivers.loc[:, ["indicator_name", "weighted_score_change"]].rename(
                columns={
                    "indicator_name": "شاخص",
                    "weighted_score_change": "تغییر امتیاز وزن‌دار",
                }
            ),
            width="stretch",
        )
    _render_indicator_charts(comparison.indicator_comparison, indicators, selected_id)


def _network_display_tables(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    important_columns = {
        BRANCH_ID: "کد شعبه",
        BRANCH_NAME: "نام شعبه",
        REGION: "منطقه",
        "baseline_rank": "رتبه مبنا",
        "scenario_rank": "رتبه سناریو",
        "rank_change": "تغییر رتبه",
        "baseline_grade": "درجه مبنا",
        "scenario_grade": "درجه سناریو",
    }
    important = frame.loc[:, list(important_columns)].rename(columns=important_columns).copy()
    important["درجه مبنا"] = important["درجه مبنا"].map(format_grade)
    important["درجه سناریو"] = important["درجه سناریو"].map(format_grade)
    detail_columns = {
        BRANCH_ID: "کد شعبه",
        BRANCH_NAME: "نام شعبه",
        "baseline_score": "امتیاز مبنا",
        "scenario_score": "امتیاز سناریو",
        "score_change": "تغییر امتیاز",
        "grade_changed": "تغییر درجه",
    }
    details = frame.loc[:, list(detail_columns)].rename(columns=detail_columns).copy()
    details["امتیاز مبنا"] = details["امتیاز مبنا"].map(format_score)
    details["امتیاز سناریو"] = details["امتیاز سناریو"].map(format_score)
    details["تغییر امتیاز"] = details["تغییر امتیاز"].map(format_score)
    details["تغییر درجه"] = details["تغییر درجه"].map({True: "بله", False: "خیر"})
    return important, details


def _network_rank_chart(frame: pd.DataFrame, *, improvement: bool) -> None:
    title = "ده شعبه با بیشترین بهبود رتبه" if improvement else "ده شعبه با بیشترین افت رتبه"
    prepared = prepare_network_rank_changes(frame, improvement=improvement)
    if prepared.empty:
        render_empty_state(f"شعبه‌ای برای «{title}» وجود ندارد.")
        return
    if len(prepared) == 1:
        row = prepared.iloc[0]
        movement = (
            f"+{row['magnitude']} رتبه"
            if improvement
            else f"افت {row['magnitude']} رتبه"
        )
        render_kpi_group(
            "تنها شعبه دارای تغییر",
            (
                ("شعبه", row["branch_label"], None, "off"),
                ("تغییر", movement, movement, "normal" if improvement else "inverse"),
            ),
        )
    figure = build_network_rank_chart(frame, improvement=improvement)
    if figure is not None:
        render_chart(
            figure,
            key=f"network_rank_{'improvement' if improvement else 'decline'}",
        )


def render_network_impact(comparison) -> None:
    """Render network KPIs, filterable table, download, and movement charts."""
    network = comparison.network_impact
    summary = comparison.summary
    unchanged = len(network) - int(summary["branches_with_rank_change"])
    cards = (
        ("تعداد شعب دارای تغییر رتبه", summary["branches_with_rank_change"]),
        ("تعداد شعب دارای تغییر امتیاز", summary["branches_with_score_change"]),
        ("تعداد شعب دارای تغییر درجه", summary["branches_with_grade_change"]),
        ("بیشترین بهبود رتبه", summary["largest_rank_improvement"]),
        ("بیشترین افت رتبه", summary["largest_rank_decline"]),
        ("تعداد شعب بدون تغییر رتبه", unchanged),
    )
    summary_tab, table_tab, improvement_tab, decline_tab = st.tabs(
        ["خلاصه", "جدول کامل", "بیشترین بهبود", "بیشترین افت"]
    )
    with summary_tab:
        for start in range(0, len(cards), 3):
            columns = st.columns(3)
            for column, (label, value) in zip(columns, cards[start : start + 3]):
                with column:
                    render_kpi_card(label, format_number(value))
    with table_tab:
        selected_filter = st.selectbox(
            "فیلتر جدول اثر شبکه", NETWORK_FILTERS, key="_network_filter"
        )
        filtered = filter_network_impact(network, selected_filter)
        important, details = _network_display_tables(filtered)
        render_table(
            important,
            height=430,
            column_config={
                "کد شعبه": st.column_config.TextColumn(width="small"),
                "نام شعبه": st.column_config.TextColumn(width="medium"),
                "منطقه": st.column_config.TextColumn(width="medium"),
                "رتبه مبنا": st.column_config.NumberColumn(format="%d", width="small"),
                "رتبه سناریو": st.column_config.NumberColumn(format="%d", width="small"),
                "تغییر رتبه": st.column_config.NumberColumn(format="%d", width="small"),
                "درجه مبنا": st.column_config.TextColumn(width="small"),
                "درجه سناریو": st.column_config.TextColumn(width="small"),
            },
        )
        with st.expander("جزئیات بیشتر"):
            render_table(details, height=350)
        csv_table = pd.concat(
            [important.reset_index(drop=True), details.drop(columns=["کد شعبه", "نام شعبه"]).reset_index(drop=True)],
            axis=1,
        )
        st.download_button(
            "دانلود CSV",
            data=csv_table.to_csv(index=False).encode("utf-8-sig"),
            file_name="scenario_network_impact.csv",
            mime="text/csv",
        )
    with improvement_tab:
        _network_rank_chart(network, improvement=True)
    with decline_tab:
        _network_rank_chart(network, improvement=False)


def main() -> None:
    initialize_session_state()
    apply_global_styles()
    render_page_header(
        "ساخت و اجرای سناریوی تحلیل حساسیت",
        "تغییر شاخص‌های شعب و بررسی اثر آن بر امتیاز، رتبه و درجه",
    )
    try:
        baseline_df, baseline_outputs = load_baseline_data(DATA_FILE)
    except (FileNotFoundError, ValueError, OSError):
        st.error("اطلاعات مبنا بارگذاری نشد. لطفاً فایل داده و ساختار ستون‌ها را بررسی کنید.")
        st.stop()
    st.session_state["baseline_outputs"] = baseline_outputs
    try:
        persistence_service = get_scenario_service(ROOT)
    except (FileNotFoundError, ValueError, OSError):
        st.error("سرویس ذخیره‌سازی سناریو در دسترس نیست. تنظیمات کاربر محلی را بررسی کنید.")
        st.stop()

    definition_tab, results_tab, network_tab = st.tabs(
        ["تعریف سناریو", "نتایج شعب منتخب", "اثر بر شبکه"]
    )
    with definition_tab:
        scenario_name, user_branch_id, other_ids, selected_ids = _settings(
            baseline_df, persistence_service
        )
        render_persistence_status(persistence_service)
        if user_branch_id is None:
            st.info("برای شروع، حداقل یک شعبه را انتخاب کنید.")
        else:
            render_baseline_summary(baseline_outputs.final_result, selected_ids)
            if st.session_state["scenario_mode"] == "ONLY_USER_BRANCH":
                preview, definition = _render_user_only_preview(
                    baseline_df, user_branch_id
                )
            elif not other_ids:
                st.warning("حداقل یک شعبه دیگر برای دامنه تغییر انتخاب کنید.")
                preview, definition = _render_user_only_preview(
                    baseline_df, user_branch_id
                )
            else:
                preview, definition = _render_rule_preview(
                    baseline_df, user_branch_id, other_ids, persistence_service
                )
            actions = st.columns([1, 1, 3])
            with actions[0]:
                submitted = st.button(
                    "اجرای سناریو",
                    type="primary",
                    disabled=(
                        not preview.is_valid
                        or (
                            st.session_state["scenario_mode"] == "USER_AND_OTHERS"
                            and not other_ids
                        )
                    ),
                    width="content",
                )
            with actions[1]:
                save_draft = st.button("ذخیره پیش‌نویس", width="content")
            if save_draft:
                try:
                    _save_draft(
                        persistence_service,
                        preview.changes,
                        definition,
                        scenario_name,
                        selected_ids,
                    )
                except Exception as exc:
                    _show_persistence_error(exc)
                else:
                    st.success("پیش‌نویس سناریو ذخیره شد.")
            if submitted:
                if save_draft:
                    st.info("پیش‌نویس ذخیره شد؛ برای اجرا دوباره دکمه اجرا را بزنید.")
                try:
                    execution = execute_generated_changes(
                        baseline_df, baseline_outputs, preview.changes, scenario_name, selected_ids
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.update(
                        {
                            "scenario_name": scenario_name.strip(),
                            "selected_regions": st.session_state["selected_regions"],
                            "selected_branch_ids": list(selected_ids),
                            "scenario_definition": definition,
                            "scenario_changes": execution.changes,
                            "scenario_dataframe": execution.scenario_dataframe,
                            "baseline_outputs": baseline_outputs,
                            "scenario_outputs": execution.scenario_outputs,
                            "scenario_results": execution.scenario_outputs,
                            "comparison_results": execution.comparison_results,
                            "scenario_executed": True,
                            "current_scenario_dirty": True,
                            "loaded_scenario_changes": [],
                            "loaded_scenario_edit_modes": {},
                            "_selected_result_branch_id": user_branch_id,
                        }
                    )
                    st.success("سناریو با موفقیت اجرا شد.")

            if st.session_state["scenario_executed"]:
                    st.markdown("#### ذخیره نتیجه")
                    save_columns = st.columns([1, 1, 3])
                    with save_columns[0]:
                        save_result = st.button(
                            "ذخیره نتیجه اجرا",
                            key="_save_executed",
                            width="content",
                            disabled=False,
                        )
                    with save_columns[1]:
                        save_new = st.button(
                            "ذخیره به‌عنوان نسخه جدید",
                            key="_save_new_version",
                            width="content",
                        )
                    if save_result or save_new:
                        try:
                            saved = _save_executed(
                                persistence_service,
                                save_as_new=save_new,
                            )
                        except Exception as exc:
                            _show_persistence_error(exc)
                        else:
                            st.success(
                                "نتیجه سناریو به‌عنوان نسخه جدید ذخیره شد."
                                if save_new
                                else "نتیجه اجرای سناریو ذخیره شد."
                            )

    with results_tab:
        if st.session_state["scenario_executed"]:
            render_selected_branch_results(
                st.session_state["comparison_results"],
                st.session_state["selected_branch_ids"],
                persistence_service.current_user.branch_id,
            )
        else:
            render_empty_state("پس از اجرای سناریو، نتایج شعب منتخب در این بخش نمایش داده می‌شود.")

    with network_tab:
        if st.session_state["scenario_executed"]:
            render_network_impact(st.session_state["comparison_results"])
        else:
            render_empty_state("پس از اجرای سناریو، اثر آن بر کل شبکه در این بخش نمایش داده می‌شود.")


main()
