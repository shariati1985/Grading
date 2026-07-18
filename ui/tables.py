"""Reusable styled table renderers."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def render_table(
    frame: pd.DataFrame,
    *,
    height: int,
    column_config: dict[str, Any] | None = None,
) -> None:
    """Render a fixed-height, index-free, full-width table."""
    st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        height=height,
        column_config=column_config,
    )


def render_indicator_values_table(frame: pd.DataFrame) -> None:
    """Render raw indicator values with explicit readable widths."""
    render_table(
        frame,
        height=345,
        column_config={
            "شاخص": st.column_config.TextColumn(width="medium"),
            "مقدار مبنا": st.column_config.TextColumn(width="large"),
            "مقدار سناریو": st.column_config.TextColumn(width="large"),
            "تغییر": st.column_config.TextColumn(width="large"),
            "درصد تغییر": st.column_config.TextColumn(width="small"),
        },
    )


def render_indicator_scores_table(frame: pd.DataFrame) -> None:
    """Render indicator score/rank results with explicit widths."""
    render_table(
        frame,
        height=345,
        column_config={
            "شاخص": st.column_config.TextColumn(width="medium"),
            "امتیاز مبنا": st.column_config.TextColumn(width="small"),
            "امتیاز سناریو": st.column_config.TextColumn(width="small"),
            "رتبه مبنا": st.column_config.TextColumn(width="small"),
            "رتبه سناریو": st.column_config.TextColumn(width="small"),
            "تغییر رتبه": st.column_config.TextColumn(width="medium"),
        },
    )
