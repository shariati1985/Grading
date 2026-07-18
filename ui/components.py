"""Reusable Streamlit presentation components."""

from __future__ import annotations

import html
from typing import Any, Iterable

import streamlit as st


def render_page_header(title: str, subtitle: str) -> None:
    """Render a consistent title and subtitle."""
    st.title(title)
    st.markdown(f'<p class="page-subtitle">{html.escape(subtitle)}</p>', unsafe_allow_html=True)


def render_kpi_card(
    label: str,
    value: object,
    delta: str | None = None,
    delta_color: str = "normal",
) -> None:
    """Render a native metric inside the shared visual system."""
    st.metric(label=label, value=str(value), delta=delta, delta_color=delta_color)


def render_kpi_group(
    title: str,
    items: Iterable[tuple[str, object, str | None, str]],
) -> None:
    """Render related metrics in one wide, non-wrapping result panel."""
    item_list = list(items)
    cells: list[str] = []
    for label, value, delta, delta_color in item_list:
        if delta_color == "off" or delta is None:
            delta_class = "neutral"
        elif delta_color == "inverse":
            delta_class = "danger"
        else:
            delta_class = "success"
        delta_html = (
            f'<div class="kpi-panel-delta {delta_class}">{html.escape(str(delta))}</div>'
            if delta is not None
            else ""
        )
        cells.append(
            '<div class="kpi-panel-item">'
            f'<div class="kpi-panel-label">{html.escape(str(label))}</div>'
            f'<div class="kpi-panel-value">{html.escape(str(value))}</div>'
            f"{delta_html}</div>"
        )
    markup = (
        f'<div class="kpi-panel"><div class="kpi-panel-title">{html.escape(title)}</div>'
        f'<div class="kpi-panel-grid" style="--kpi-count:{len(item_list)}">'
        + "".join(cells)
        + "</div></div>"
    )
    st.markdown(markup, unsafe_allow_html=True)


def apply_plotly_layout(
    figure: Any,
    *,
    title: str,
    height: int = 480,
    show_legend: bool = True,
    left_margin: int = 170,
) -> Any:
    """Apply the shared Persian-friendly Plotly visual system."""
    figure.update_layout(
        title={"text": title, "x": 0.98, "xanchor": "right", "font": {"size": 18}},
        height=height,
        autosize=True,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"family": 'Tahoma, Arial, "Segoe UI", sans-serif', "size": 13, "color": "#344054"},
        margin={"l": left_margin, "r": 32, "t": 68, "b": 55},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "left", "x": 0},
        showlegend=show_legend,
        hoverlabel={"font": {"family": 'Tahoma, Arial, "Segoe UI", sans-serif'}},
    )
    figure.update_xaxes(showgrid=True, gridcolor="#edf0f5", zerolinecolor="#98a2b3")
    figure.update_yaxes(showgrid=False, automargin=True)
    return figure


def render_plotly_chart(figure: Any) -> None:
    """Render a responsive Plotly chart without the visual toolbar."""
    st.plotly_chart(
        figure,
        width="stretch",
        config={"displayModeBar": False, "responsive": True, "displaylogo": False},
    )


def render_navigation_card(title: str, description: str, page_path: str) -> None:
    """Render a navigation card that uses Streamlit's native page link."""
    with st.container(border=True):
        st.subheader(title)
        st.write(description)
        st.page_link(page_path, label=f"ورود به {title}", icon="◀️")


def render_empty_state(message: str) -> None:
    """Render a consistent informational empty state."""
    with st.container(border=True):
        st.info(message, icon="ℹ️")


def render_branch_identity(branch_id: str, branch_name: str, region: str) -> None:
    """Render a safe, compact branch identity block."""
    content = (
        f"<strong>{html.escape(branch_name)}</strong> "
        f"<span>({html.escape(branch_id)})</span><br>"
        f"<small>منطقه: {html.escape(region)}</small>"
    )
    st.markdown(f'<div class="branch-identity">{content}</div>', unsafe_allow_html=True)
