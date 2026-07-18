"""Custom Persian navigation for the application shell."""

from __future__ import annotations

from typing import Final

import streamlit as st

NAVIGATION_ITEMS: Final[tuple[tuple[str, str, str], ...]] = (
    ("▦", "داشبورد", "pages/1_Dashboard.py"),
    ("✦", "ساخت سناریو", "pages/2_Scenario_Builder.py"),
    ("◉", "نتایج سناریو", "pages/3_Scenario_Results.py"),
    ("⌁", "اثر بر شبکه", "pages/4_Network_Impact.py"),
    ("⇄", "مقایسه سناریوها", "pages/5_Scenario_Comparison.py"),
    ("▤", "گزارش‌ها", "pages/6_Reports.py"),
)


def _page_link(path: str, label: str) -> None:
    """Render a native link, with a bare-mode fallback for isolated page tests."""
    try:
        st.page_link(path, label=label)
    except KeyError:
        st.markdown(f"<div class='nav-test-label'>{label}</div>", unsafe_allow_html=True)


def render_navigation() -> None:
    """Render native page links inside the custom right navigation panel."""
    with st.sidebar:
        st.markdown(
            '<div class="nav-brand"><span class="nav-brand-mark">EN</span>'
            '<div><strong>تحلیل حساسیت شعب</strong><small>سامانه درجه‌بندی</small></div></div>',
            unsafe_allow_html=True,
        )
        _page_link("app.py", "⌂  خانه")
        for icon, label, page_path in NAVIGATION_ITEMS:
            _page_link(page_path, f"{icon}  {label}")
