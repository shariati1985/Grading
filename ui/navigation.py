"""Custom Persian navigation for the application shell."""

from __future__ import annotations

import html
from urllib.parse import quote

import streamlit as st

from domain.scenario_contracts import ScenarioType
from ui.sensitivity_labels import SCENARIO_DEFINITIONS
from ui.sensitivity_state import SENSITIVITY_DRAFT_KEY, start_new_scenario

NAVIGATION_ITEMS = tuple(
    (item.icon, item.label, item.scenario_type) for item in SCENARIO_DEFINITIONS
)
UTILITY_NAVIGATION_ITEMS = (
    ("⌂", "صفحه اصلی", "/"),
    ("▤", "سناریوهای ذخیره‌شده", "/?view=saved#saved-scenarios"),
)


def scenario_href(mode: ScenarioType) -> str:
    return f"/?scenario={quote(mode.value)}&new=1"


def scenario_mode_from_query(value: object) -> ScenarioType | None:
    try:
        return ScenarioType(str(value)) if value else None
    except ValueError:
        return None


def activate_requested_scenario() -> bool:
    """Consume a scenario query selection, update state, and open its form."""
    raw = st.query_params.get("scenario")
    if not raw:
        return False
    mode = scenario_mode_from_query(raw)
    if mode is None:
        st.query_params.clear()
        return False
    st.query_params.clear()
    start_new_scenario(st.session_state, mode)
    st.switch_page("pages/2_Scenario_Builder.py")
    return True


def render_navigation() -> None:
    """Render native page links inside the custom right navigation panel."""
    with st.sidebar:
        st.markdown(
            '<div class="nav-brand"><span class="nav-brand-mark" role="img" aria-label="بانک اقتصاد نوین"></span>'
            '<div><strong>تحلیل حساسیت شعب</strong><small>سامانه درجه‌بندی</small></div></div>',
            unsafe_allow_html=True,
        )
        utility_links = "".join(
            f'<a class="scenario-nav-link" href="{href}" target="_self">{html.escape(icon)} '
            f'<span>{html.escape(label)}</span></a>'
            for icon, label, href in UTILITY_NAVIGATION_ITEMS
        )
        st.markdown(f'<nav class="utility-nav">{utility_links}</nav>', unsafe_allow_html=True)
        current = st.session_state.get(SENSITIVITY_DRAFT_KEY, {}).get("scenario_type")
        links = []
        for item in SCENARIO_DEFINITIONS:
            active = " active" if current is item.scenario_type else ""
            links.append(
                f'<a class="scenario-nav-link{active}" href="{scenario_href(item.scenario_type)}" '
                f'target="_self"><span>{html.escape(item.icon)}</span>{html.escape(item.label)}</a>'
            )
        st.markdown(f'<nav class="scenario-nav">{"".join(links)}</nav>', unsafe_allow_html=True)
