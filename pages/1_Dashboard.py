"""Baseline network dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd
import plotly.express as px
import streamlit as st

from engine.ranking_engine import BRANCH_ID, BRANCH_NAME, REGION
from ui import initialize_session_state
from ui.components import render_empty_state, render_kpi_card, render_page_header
from ui.charts import apply_chart_layout, render_chart
from ui.data_access import load_dashboard_data
from ui.formatters import format_grade, format_number, format_score
from ui.styles import apply_global_styles
from ui.tables import render_table

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
DATA_FILE: Final[Path] = ROOT / "Data.xlsx"
PERIOD: Final[str] = "1404-04"
ALL_REGIONS: Final[str] = "همه مناطق"
ALL_GRADES: Final[str] = "همه درجات"


@st.cache_data(show_spinner="در حال محاسبه وضعیت مبنا...")
def get_dashboard_data(data_file: Path, period: str):
    """Return cached canonical data and baseline model outputs."""
    return load_dashboard_data(data_file, period)


def _display_table(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.loc[:, [BRANCH_ID, BRANCH_NAME, REGION, "final_score", "rank", "grade"]].copy()
    display["final_score"] = display["final_score"].map(format_score)
    display["grade"] = display["grade"].replace({"Excellent Plus": "Excellent"}).map(format_grade)
    return display.rename(
        columns={
            BRANCH_ID: "کد شعبه",
            BRANCH_NAME: "نام شعبه",
            REGION: "منطقه",
            "final_score": "امتیاز نهایی",
            "rank": "رتبه",
            "grade": "درجه",
        }
    )


def main() -> None:
    initialize_session_state()
    apply_global_styles()
    render_page_header("داشبورد", "نمای کلی وضعیت رتبه‌بندی شعب در دوره مبنا")

    try:
        baseline_data, outputs = get_dashboard_data(DATA_FILE, PERIOD)
    except (FileNotFoundError, ValueError, OSError) as exc:
        st.error(f"خطا در بارگذاری داشبورد: {exc}")
        st.stop()

    result = outputs.final_result.copy()
    result["ui_grade"] = result["grade"].replace({"Excellent Plus": "Excellent"})
    with st.container(border=True):
        st.markdown("### فیلترهای داشبورد")
        filter_columns = st.columns(3)
        with filter_columns[0]:
            selected_region = st.selectbox(
                "منطقه", options=[ALL_REGIONS, *sorted(baseline_data[REGION].unique())]
            )
        with filter_columns[1]:
            selected_grade = st.selectbox(
                "درجه",
                options=[ALL_GRADES, *result["ui_grade"].drop_duplicates().tolist()],
                format_func=lambda value: value if value == ALL_GRADES else format_grade(value),
            )
        with filter_columns[2]:
            selected_period = st.selectbox("دوره", options=[PERIOD])
        st.caption(f"دوره انتخاب‌شده: {selected_period}")

    filtered = result.copy()
    if selected_region != ALL_REGIONS:
        filtered = filtered.loc[filtered[REGION].eq(selected_region)]
    if selected_grade != ALL_GRADES:
        filtered = filtered.loc[filtered["ui_grade"].eq(selected_grade)]

    if filtered.empty:
        render_empty_state("برای ترکیب فیلترهای انتخاب‌شده شعبه‌ای وجود ندارد.")
        return

    best = filtered.sort_values("rank").iloc[0]
    kpis = (
        ("تعداد شعب", format_number(len(filtered))),
        ("تعداد مناطق", format_number(filtered[REGION].nunique())),
        ("میانگین امتیاز", format_score(filtered["final_score"].mean())),
        ("بالاترین امتیاز", format_score(filtered["final_score"].max())),
        ("پایین‌ترین امتیاز", format_score(filtered["final_score"].min())),
        ("بهترین شعبه", f"{best[BRANCH_NAME]} ({best[BRANCH_ID]})"),
    )
    for start in range(0, len(kpis), 3):
        columns = st.columns(3)
        for column, (label, value) in zip(columns, kpis[start : start + 3]):
            with column:
                render_kpi_card(label, value)

    chart_left, chart_right = st.columns(2)
    grade_counts = filtered["ui_grade"].value_counts().rename_axis("grade").reset_index(name="count")
    grade_counts["درجه"] = grade_counts["grade"].map(format_grade)
    with chart_left:
        st.subheader("توزیع درجه‌ها")
        figure = px.bar(
            grade_counts,
            x="درجه",
            y="count",
            labels={"count": "تعداد شعب", "درجه": "درجه"},
            color="درجه",
            color_discrete_sequence=px.colors.sequential.Blues_r,
        )
        apply_chart_layout(figure, title="توزیع درجات", height=420, show_legend=False, left_margin=70)
        render_chart(figure, key="dashboard_grade_distribution")

    region_counts = filtered[REGION].value_counts().rename_axis(REGION).reset_index(name="count")
    with chart_right:
        st.subheader("تعداد شعب به تفکیک منطقه")
        figure = px.bar(
            region_counts.sort_values("count"),
            x="count",
            y=REGION,
            orientation="h",
            labels={"count": "تعداد شعب", REGION: "منطقه"},
            color="count",
            color_continuous_scale="Blues",
        )
        figure.update_layout(coloraxis_showscale=False)
        figure.update_xaxes(dtick=1)
        apply_chart_layout(
            figure,
            title="تعداد شعب به تفکیک منطقه",
            height=420,
            show_legend=False,
            left_margin=120,
        )
        render_chart(figure, key="dashboard_top_branch_scores")

    top_column, bottom_column = st.columns(2)
    with top_column:
        st.subheader("۱۰ شعبه برتر")
        render_table(_display_table(filtered.nsmallest(10, "rank")), height=410)
    with bottom_column:
        st.subheader("۱۰ شعبه انتهایی")
        render_table(_display_table(filtered.nlargest(10, "rank").sort_values("rank")), height=410)


main()
