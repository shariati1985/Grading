"""Complete interactive sensitivity-analysis Scenario Builder."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd
import streamlit as st

from engine.ranking_engine import BRANCH_ID, BRANCH_NAME, REGION, ModelOutputs
from persistence.contracts import ConcurrencyError, ScenarioPersistenceError
from persistence.models import ScenarioRecord
from services.factory import create_local_scenario_service
from services.scenario_management_service import ScenarioManagementService
from ui import initialize_session_state
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
ALL_REGIONS: Final[str] = "همه مناطق"


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


def _settings(baseline_df: pd.DataFrame) -> tuple[str, str, list[str], str]:
    """Render top-of-page scenario settings."""
    if "_scenario_name_input" not in st.session_state:
        st.session_state["_scenario_name_input"] = st.session_state["scenario_name"]
    if "_selected_region_input" not in st.session_state:
        saved = st.session_state["selected_regions"]
        st.session_state["_selected_region_input"] = saved[0] if saved else ALL_REGIONS
    if "_scenario_visibility" not in st.session_state:
        record = st.session_state["current_scenario_record"]
        st.session_state["_scenario_visibility"] = (
            record.visibility if record is not None else "private"
        )

    name_column, period_column, region_column, reset_column = st.columns([2.2, 1, 1.5, 1])
    with name_column:
        scenario_name = st.text_input(
            "نام سناریو",
            key="_scenario_name_input",
            placeholder="برای مثال: رشد ۱۰ درصدی سپرده‌ها",
        )
    with period_column:
        st.selectbox("دوره انتخابی", options=[MODEL_PERIOD], disabled=True)
    with region_column:
        selected_region = st.selectbox(
            "منطقه",
            options=[ALL_REGIONS, *sorted(baseline_df[REGION].unique().tolist())],
            key="_selected_region_input",
        )
    with reset_column:
        st.write("")
        st.write("")
        st.button("بازنشانی", width="stretch", on_click=reset_scenario)

    st.session_state["selected_regions"] = (
        [] if selected_region == ALL_REGIONS else [selected_region]
    )
    available = (
        baseline_df
        if selected_region == ALL_REGIONS
        else baseline_df.loc[baseline_df[REGION].eq(selected_region)]
    )
    available_ids = available[BRANCH_ID].tolist()
    current_ids = st.session_state.get(
        "_selected_branches_input", st.session_state["selected_branches"]
    )
    st.session_state["_selected_branches_input"] = [
        branch_id for branch_id in current_ids if branch_id in available_ids
    ]
    names = available.set_index(BRANCH_ID)[BRANCH_NAME].to_dict()
    selected_ids = st.multiselect(
        "انتخاب شعب",
        options=available_ids,
        format_func=lambda branch_id: f"{names[branch_id]} ({branch_id})",
        key="_selected_branches_input",
        placeholder="نام یا کد شعبه را جست‌وجو کنید",
    )
    visibility = st.radio(
        "اشتراک‌گذاری سناریو",
        options=["private", "shared"],
        format_func=lambda value: "شخصی" if value == "private" else "مشترک",
        horizontal=True,
        key="_scenario_visibility",
    )
    return scenario_name, selected_region, selected_ids, visibility


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
    editor_state: dict[str, dict[str, object]],
    scenario_name: str,
    visibility: str,
    selected_ids: list[str],
) -> None:
    changes = build_scenario_changes_from_editor_state(editor_state)
    record = service.save_draft(
        scenario_name=scenario_name,
        baseline_period=MODEL_PERIOD,
        visibility=visibility,
        selected_branch_ids=selected_ids,
        changes=changes,
        scenario_id=st.session_state["current_scenario_id"],
        expected_row_version=st.session_state["current_scenario_row_version"],
        edit_modes=editor_edit_modes(editor_state),
    )
    _store_saved_record(record)
    st.session_state.update(
        {
            "scenario_name": scenario_name.strip(),
            "selected_branches": list(selected_ids),
            "scenario_changes": changes,
            "scenario_dataframe": None,
            "scenario_outputs": None,
            "comparison_results": None,
            "scenario_executed": False,
            "loaded_scenario_changes": changes,
            "loaded_scenario_edit_modes": editor_edit_modes(editor_state),
        }
    )


def _save_executed(
    service: ScenarioManagementService,
    visibility: str,
    *,
    save_as_new: bool,
) -> ScenarioRecord:
    record = service.save_executed(
        scenario_name=st.session_state["scenario_name"],
        baseline_period=MODEL_PERIOD,
        visibility=visibility,
        selected_branch_ids=st.session_state["selected_branches"],
        changes=st.session_state["scenario_changes"],
        comparison=st.session_state["comparison_results"],
        scenario_id=st.session_state["current_scenario_id"],
        expected_row_version=st.session_state["current_scenario_row_version"],
        save_as_new=save_as_new,
        edit_modes=editor_edit_modes(st.session_state["indicator_editor_state"]),
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
            "baseline_indicator_rank",
            "scenario_indicator_rank",
            "indicator_rank_change",
        ],
    ].rename(
        columns={
            "indicator_key": "شاخص",
            "baseline_score": "امتیاز مبنا",
            "scenario_score": "امتیاز سناریو",
            "baseline_indicator_rank": "رتبه مبنا",
            "scenario_indicator_rank": "رتبه سناریو",
            "indicator_rank_change": "تغییر رتبه",
        }
    )
    scores["امتیاز مبنا"] = scores["امتیاز مبنا"].map(format_score)
    scores["امتیاز سناریو"] = scores["امتیاز سناریو"].map(format_score)
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
    render_chart(score_figure)

    chart_data = indicators.copy()
    order = {key: index for index, key in enumerate(INDICATOR_ORDER)}
    chart_data["_order"] = chart_data["indicator_key"].map(order)
    chart_data = chart_data.sort_values("_order")
    labels = chart_data["indicator_key"].map(INDICATOR_LABELS)
    rank_figure = build_indicator_rank_lollipop(
        labels,
        chart_data["indicator_rank_change"],
    )
    render_chart(rank_figure)


def render_selected_branch_results(comparison, selected_ids: list[str]) -> None:
    """Render branch and indicator comparisons for every selected branch."""
    branches = selected_branch_results(comparison, selected_ids)
    tabs = st.tabs([f"{row[BRANCH_NAME]} ({row[BRANCH_ID]})" for _, row in branches.iterrows()])
    for tab, (_, branch) in zip(tabs, branches.iterrows()):
        with tab:
            _render_branch_kpis(branch)
            indicators = comparison.indicator_comparison.loc[
                comparison.indicator_comparison[BRANCH_ID].eq(branch[BRANCH_ID])
            ].copy()
            st.subheader("مقایسه شاخص‌ها")
            values, scores = _indicator_tables(indicators)
            value_tab, score_tab = st.tabs(["مقادیر شاخص‌ها", "امتیاز و رتبه شاخص‌ها"])
            with value_tab:
                render_indicator_values_table(values)
            with score_tab:
                render_indicator_scores_table(scores)
            _render_indicator_charts(
                comparison.indicator_comparison,
                indicators,
                str(branch[BRANCH_ID]),
            )


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
        render_chart(figure)


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
        scenario_name, selected_region, selected_ids, visibility = _settings(baseline_df)
        del selected_region
        render_persistence_status(persistence_service)
        selection = tuple(selected_ids)
        if (
            st.session_state.get("_editor_branches") != selection
            or (selected_ids and not st.session_state["indicator_editor_state"])
        ):
            st.session_state["_editor_branches"] = selection
            st.session_state["editor_version"] = st.session_state.get("editor_version", 0) + 1
            _clear_editor_widget_state()
            if selected_ids:
                baseline_rows = build_editor_data(baseline_df, selected_ids)
                state = build_indicator_editor_state(baseline_rows)
                state = restore_indicator_editor_state(
                    state,
                    st.session_state["loaded_scenario_changes"],
                    st.session_state["loaded_scenario_edit_modes"],
                )
                st.session_state["indicator_editor_state"] = state

        if not selected_ids:
            st.info("برای شروع، حداقل یک شعبه را انتخاب کنید.")
        else:
            try:
                render_baseline_summary(baseline_outputs.final_result, selected_ids)
                current_record = st.session_state["current_scenario_record"]
                can_update = (
                    current_record is None
                    or current_record.owner_user_id == persistence_service.current_user.user_id
                )
                editor_state, submitted, save_draft = render_scenario_editor(
                    st.session_state["indicator_editor_state"], can_update=can_update
                )
                if not can_update:
                    st.info(
                        "این سناریوی مشترک متعلق به کاربر دیگری است؛ برای ذخیره تغییرات، "
                        "از «ذخیره به‌عنوان نسخه جدید» استفاده کنید."
                    )
            except ValueError as exc:
                st.error(str(exc))
            else:
                if save_draft:
                    try:
                        _save_draft(
                            persistence_service,
                            editor_state,
                            scenario_name,
                            visibility,
                            selected_ids,
                        )
                    except Exception as exc:
                        _show_persistence_error(exc)
                    else:
                        st.success("پیش‌نویس سناریو ذخیره شد.")
                if submitted:
                    try:
                        execution = execute_scenario_from_editor_state(
                            baseline_df,
                            baseline_outputs,
                            editor_state,
                            scenario_name,
                            selected_ids,
                        )
                    except ValueError as exc:
                        st.error(str(exc))
                    except Exception:
                        st.error(
                            "خطای غیرمنتظره‌ای در اجرای سناریو رخ داد. "
                            "لطفاً ورودی‌ها را بررسی و دوباره تلاش کنید."
                        )
                    else:
                        st.session_state.update(
                            {
                                "scenario_name": scenario_name.strip(),
                                "selected_regions": st.session_state["selected_regions"],
                                "selected_branches": list(selected_ids),
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
                            disabled=not can_update,
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
                                visibility,
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
                st.session_state["selected_branches"],
            )
        else:
            render_empty_state("پس از اجرای سناریو، نتایج شعب منتخب در این بخش نمایش داده می‌شود.")

    with network_tab:
        if st.session_state["scenario_executed"]:
            render_network_impact(st.session_state["comparison_results"])
        else:
            render_empty_state("پس از اجرای سناریو، اثر آن بر کل شبکه در این بخش نمایش داده می‌شود.")


main()
