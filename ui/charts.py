"""Reusable Plotly builders for the banking visual system."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.ranking_engine import BRANCH_ID
from ui.scenario_workflow import INDICATOR_LABELS, INDICATOR_ORDER

FONT_FAMILY = '"Segoe UI", Tahoma, Arial, sans-serif'
INDICATOR_SCORE_COLUMNS = (
    BRANCH_ID,
    "indicator_key",
    "baseline_score",
    "scenario_score",
)


class IndicatorComparisonDataError(RuntimeError):
    """Raised when indicator comparison rows cannot safely drive the chart."""


def prepare_selected_indicator_scores(
    indicator_comparison: pd.DataFrame, selected_branch_id: str
) -> pd.DataFrame:
    """Select and order one branch's exact unweighted indicator scores."""
    missing = set(INDICATOR_SCORE_COLUMNS) - set(indicator_comparison.columns)
    if missing:
        raise IndicatorComparisonDataError(
            "Internal indicator comparison error: missing columns: "
            + ", ".join(sorted(missing))
        )
    duplicate_mask = indicator_comparison.duplicated(
        [BRANCH_ID, "indicator_key"], keep=False
    )
    if duplicate_mask.any():
        duplicate = indicator_comparison.loc[
            duplicate_mask, [BRANCH_ID, "indicator_key"]
        ].iloc[0]
        raise IndicatorComparisonDataError(
            "Internal indicator comparison error: duplicate branch_id + "
            f"indicator_key row ({duplicate[BRANCH_ID]}, {duplicate['indicator_key']})."
        )

    selected = indicator_comparison.loc[
        indicator_comparison[BRANCH_ID].astype(str).eq(str(selected_branch_id)),
        list(INDICATOR_SCORE_COLUMNS),
    ].copy()
    keys = selected["indicator_key"].astype(str).tolist()
    missing_indicators = [key for key in INDICATOR_ORDER if key not in keys]
    unexpected = [key for key in keys if key not in INDICATOR_ORDER]
    if missing_indicators or unexpected or len(selected) != len(INDICATOR_ORDER):
        details = []
        if missing_indicators:
            details.append("missing: " + ", ".join(missing_indicators))
        if unexpected:
            details.append("unexpected: " + ", ".join(unexpected))
        raise IndicatorComparisonDataError(
            "Internal indicator comparison error: selected branch must have exactly "
            "one row for each of the eight indicators"
            + (" (" + "; ".join(details) + ")" if details else "")
            + "."
        )

    for column in ("baseline_score", "scenario_score"):
        numeric = pd.to_numeric(selected[column], errors="coerce")
        if numeric.isna().any() or not numeric.between(1, 1000).all():
            raise IndicatorComparisonDataError(
                f"Internal indicator comparison error: {column} must be within 1–1000."
            )
    order = {key: position for position, key in enumerate(INDICATOR_ORDER)}
    selected["_order"] = selected["indicator_key"].map(order)
    return selected.sort_values("_order").drop(columns="_order").reset_index(drop=True)


def validate_indicator_score_chart_matches_table(
    chart_scores: pd.DataFrame, table_scores: pd.DataFrame
) -> None:
    """Validate exact score equality between chart and table source rows."""
    missing = set(INDICATOR_SCORE_COLUMNS) - set(table_scores.columns)
    if missing:
        raise IndicatorComparisonDataError(
            "Internal indicator comparison error: table source is missing columns: "
            + ", ".join(sorted(missing))
        )
    table = table_scores.loc[:, list(INDICATOR_SCORE_COLUMNS)].copy()
    if table.duplicated([BRANCH_ID, "indicator_key"]).any():
        raise IndicatorComparisonDataError(
            "Internal indicator comparison error: duplicate branch_id + indicator_key "
            "row in table source."
        )
    chart = chart_scores.loc[:, list(INDICATOR_SCORE_COLUMNS)].reset_index(drop=True)
    order = {key: position for position, key in enumerate(INDICATOR_ORDER)}
    table["_order"] = table["indicator_key"].map(order)
    table = table.sort_values("_order").drop(columns="_order").reset_index(drop=True)
    if not chart.equals(table):
        raise IndicatorComparisonDataError(
            "Internal indicator comparison error: chart scores do not match the "
            "indicator comparison table."
        )


def rank_axis_range(values: pd.Series | list[float] | np.ndarray) -> tuple[int, int]:
    """Return a symmetric integer rank axis with a minimum -3..+3 range."""
    numeric = pd.to_numeric(pd.Series(values, dtype="float64"), errors="coerce").dropna()
    maximum = float(numeric.abs().max()) if not numeric.empty else 0.0
    extent = max(3, int(math.ceil(maximum)))
    return -extent, extent


def apply_chart_layout(
    figure: Any,
    *,
    title: str,
    height: int,
    show_legend: bool = True,
    left_margin: int = 180,
) -> Any:
    """Apply consistent typography, spacing, backgrounds, and hover styling."""
    figure.update_layout(
        title={"text": title, "x": 0.98, "xanchor": "right", "font": {"size": 17}},
        height=height,
        autosize=True,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font={"family": FONT_FAMILY, "size": 13, "color": "#344054"},
        margin={"l": left_margin, "r": 42, "t": 66, "b": 48},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "x": 0},
        showlegend=show_legend,
        hoverlabel={"font": {"family": FONT_FAMILY}},
    )
    figure.update_xaxes(showgrid=True, gridcolor="#EEF1F6", zerolinecolor="#98A2B3")
    figure.update_yaxes(showgrid=False, automargin=True)
    return figure


def render_chart(figure: Any, *, key: str) -> None:
    """Render a full-width responsive chart without the toolbar."""
    st.plotly_chart(
        figure,
        key=key,
        width="stretch",
        config={"displayModeBar": False, "responsive": True, "displaylogo": False},
    )


def build_score_comparison_chart(
    labels: pd.Series,
    baseline_scores: pd.Series,
    scenario_scores: pd.Series,
) -> go.Figure:
    """Build the eight-indicator horizontal score comparison."""
    figure = go.Figure(
        [
            go.Bar(
                name="امتیاز مبنا",
                y=labels,
                x=baseline_scores,
                orientation="h",
                marker_color="#98A2B3",
                hovertemplate="%{y}<br>مبنا: %{x:.1f}<extra></extra>",
            ),
            go.Bar(
                name="امتیاز سناریو",
                y=labels,
                x=scenario_scores,
                orientation="h",
                marker_color="#6D4AFF",
                hovertemplate="%{y}<br>سناریو: %{x:.1f}<extra></extra>",
            ),
        ]
    )
    figure.update_layout(barmode="group")
    figure.update_xaxes(title="امتیاز", range=[1, 1000], tickformat=".0f")
    return apply_chart_layout(figure, title="مقایسه امتیاز شاخص‌ها", height=470)


def build_selected_indicator_score_chart(indicator_scores: pd.DataFrame) -> go.Figure:
    """Plot only the exact four-column unweighted indicator score dataset."""
    if tuple(indicator_scores.columns) != INDICATOR_SCORE_COLUMNS:
        raise IndicatorComparisonDataError(
            "Internal indicator comparison error: chart input must contain only "
            "branch_id, indicator_key, baseline_score, and scenario_score."
        )
    labels = indicator_scores["indicator_key"].map(INDICATOR_LABELS)
    if labels.isna().any():
        raise IndicatorComparisonDataError(
            "Internal indicator comparison error: unknown indicator_key in chart data."
        )
    return build_score_comparison_chart(
        labels,
        indicator_scores["baseline_score"],
        indicator_scores["scenario_score"],
    )


def build_indicator_rank_lollipop(
    labels: pd.Series, rank_changes: pd.Series
) -> go.Figure:
    """Build a centered integer-axis lollipop chart for indicator rank changes."""
    values = pd.to_numeric(rank_changes, errors="coerce").fillna(0).astype(int)
    figure = go.Figure()
    for label, value in zip(labels, values):
        color = "#178A61" if value > 0 else "#C43F3A" if value < 0 else "#98A2B3"
        figure.add_trace(
            go.Scatter(
                x=[0, value],
                y=[label, label],
                mode="lines",
                line={"color": color, "width": 3},
                hoverinfo="skip",
                showlegend=False,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[value],
                y=[label],
                mode="markers+text",
                marker={"color": color, "size": 11},
                text=[str(value)],
                textposition="middle right" if value >= 0 else "middle left",
                hovertemplate=f"{label}<br>تغییر رتبه: {value:d}<extra></extra>",
                showlegend=False,
            )
        )
    minimum, maximum = rank_axis_range(values)
    figure.update_xaxes(
        title="تغییر رتبه (مثبت = بهبود)",
        range=[minimum, maximum],
        dtick=1,
        tickformat="d",
        zeroline=True,
        zerolinewidth=2,
    )
    return apply_chart_layout(
        figure, title="تغییر رتبه شاخص‌ها", height=440, show_legend=False
    )


def prepare_network_rank_changes(
    frame: pd.DataFrame, *, improvement: bool, limit: int = 10
) -> pd.DataFrame:
    """Return ranked non-zero network movements with positive display magnitude."""
    mask = frame["rank_change"].gt(0) if improvement else frame["rank_change"].lt(0)
    prepared = frame.loc[mask].copy()
    prepared["magnitude"] = prepared["rank_change"].abs().astype(int)
    prepared = prepared.nlargest(limit, "magnitude")
    prepared["branch_label"] = (
        prepared["branch_name"].astype(str) + " (" + prepared["branch_id"].astype(str) + ")"
    )
    return prepared.reset_index(drop=True)


def build_network_rank_chart(
    frame: pd.DataFrame, *, improvement: bool
) -> go.Figure | None:
    """Build a compact zero-based network movement chart, or None if empty."""
    prepared = prepare_network_rank_changes(frame, improvement=improvement)
    if prepared.empty:
        return None
    title = "ده شعبه با بیشترین بهبود رتبه" if improvement else "ده شعبه با بیشترین افت رتبه"
    color = "#178A61" if improvement else "#C43F3A"
    text = (
        prepared["magnitude"].map(lambda value: f"+{value}")
        if improvement
        else prepared["magnitude"].map(lambda value: f"افت {value} رتبه")
    )
    figure = go.Figure(
        go.Bar(
            x=prepared["magnitude"],
            y=prepared["branch_label"],
            orientation="h",
            marker_color=color,
            text=text,
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}<br>%{text}<extra></extra>",
        )
    )
    maximum = max(1, int(prepared["magnitude"].max()))
    figure.update_xaxes(range=[0, maximum + 1], dtick=1, tickformat="d", title="تغییر رتبه")
    height = 270 if len(prepared) == 1 else max(350, min(470, 115 + len(prepared) * 34))
    return apply_chart_layout(
        figure,
        title=title,
        height=height,
        show_legend=False,
        left_margin=210,
    )


def build_impact_distribution_chart(summary: Any, *, mode: str = "combined") -> go.Figure:
    """Build compact stacked distribution bars for rank and grade outcomes."""
    total = max(1, int(summary.total_branches))
    figure = go.Figure()
    all_rows = [
        ("جابه‌جایی رتبه", [("صعود رتبه", summary.rank_up, "#16835B"), ("نزول رتبه", summary.rank_down, "#C43D4B"), ("بدون تغییر رتبه", summary.rank_same, "#687386")]),
        ("تغییر درجه", [("بهبود درجه", summary.grade_up, "#16835B"), ("افت درجه", summary.grade_down, "#C43D4B"), ("بدون تغییر درجه", summary.grade_same, "#344765")]),
    ]
    rows = all_rows if mode == "combined" else all_rows[:1] if mode == "rank" else all_rows[1:]
    for label, parts in rows:
        for name, count, color in parts:
            pct = count * 100 / total
            figure.add_trace(go.Bar(
                name=name,
                y=[label],
                x=[count],
                orientation="h",
                marker_color=color,
                text=[f"{count} ({pct:.1f}%)" if pct >= 8 else ""],
                textposition="inside" if pct >= 8 else "outside",
                hovertemplate=f"{name}<br>تعداد: %{{x:.0f}}<br>درصد جامعه: {pct:.1f}%<extra></extra>",
            ))
    figure.update_layout(barmode="stack")
    figure.update_xaxes(title="تعداد شعب", range=[0, total], tickformat="d")
    title = "توزیع جابه‌جایی رتبه" if mode == "rank" else "توزیع تغییر درجه" if mode == "grade" else "توزیع اثر سناریو بر شبکه"
    return apply_chart_layout(figure, title=title, height=280 if mode != "combined" else 300, left_margin=125)


def build_indicator_impact_chart(frame: pd.DataFrame) -> go.Figure:
    """Build affected-branch count by indicator."""
    prepared = frame.sort_values("affected_branches", ascending=True)
    figure = go.Figure(go.Bar(
        x=prepared["affected_branches"],
        y=prepared["indicator_name"],
        orientation="h",
        marker_color="#65328A",
        hovertemplate="%{y}<br>شعب متأثر: %{x:.0f}<extra></extra>",
    ))
    maximum = max(1, int(prepared["affected_branches"].max()))
    figure.update_xaxes(title="تعداد شعب دارای تغییر مقدار", range=[0, maximum + 1], tickformat="d")
    return apply_chart_layout(figure, title="اثر قواعد به تفکیک شاخص", height=max(320, 90 + len(prepared) * 42), show_legend=False, left_margin=190)


def build_multi_branch_rank_movement_chart(frame: pd.DataFrame, *, mode: str = "largest_improvements", limit: int = 15) -> go.Figure | None:
    """Show meaningful non-zero rank movements, where positive means improvement."""
    moved = frame.loc[frame["rank_change"].ne(0)].copy()
    if moved.empty:
        return None
    if mode == "largest_improvements":
        moved = moved.loc[moved["rank_change"].gt(0)].nlargest(limit, "rank_change")
        title = "بیشترین بهبودهای رتبه"
    elif mode == "largest_declines":
        moved = moved.loc[moved["rank_change"].lt(0)].nsmallest(limit, "rank_change")
        title = "بیشترین افت‌های رتبه"
    else:
        moved = moved.assign(_abs=moved["rank_change"].abs()).nlargest(limit, "_abs").drop(columns="_abs")
        title = "همه شعب دارای جابه‌جایی رتبه"
    if moved.empty:
        return None
    moved = moved.assign(
        branch_label=moved["branch_name"].astype(str) + " (" + moved["branch_id"].astype(str) + ")",
        color=moved["rank_change"].map(lambda value: "#16835B" if value > 0 else "#C43D4B"),
    ).sort_values("rank_change")
    figure = go.Figure(go.Bar(
        x=moved["rank_change"],
        y=moved["branch_label"],
        orientation="h",
        marker_color=moved["color"],
        hovertemplate="%{y}<br>جابه‌جایی رتبه: %{x:+d}<extra></extra>",
    ))
    minimum, maximum = rank_axis_range(moved["rank_change"])
    figure.update_xaxes(title="جابه‌جایی رتبه (مثبت = بهبود)", range=[minimum, maximum], dtick=1, tickformat="d", zeroline=True, zerolinewidth=2)
    return apply_chart_layout(figure, title=title, height=max(330, min(620, 120 + len(moved) * 32)), show_legend=False, left_margin=220)
