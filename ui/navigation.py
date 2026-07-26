"""Custom Persian navigation for the application shell."""

from __future__ import annotations

import base64
import html
import mimetypes
from pathlib import Path
from urllib.parse import quote

import streamlit as st

from domain.scenario_contracts import ScenarioType
from ui.sensitivity_labels import SCENARIO_DEFINITIONS
from ui.sensitivity_state import SENSITIVITY_DRAFT_KEY, start_new_scenario

NAVIGATION_ITEMS = tuple(
    (item.icon, item.label, item.scenario_type) for item in SCENARIO_DEFINITIONS
)
ROOT = Path(__file__).resolve().parents[1]
EN_BANK_LOGO_RELATIVE_PATH = Path("assets") / "logo-1.png"
EN_BANK_LOGO_PATH = ROOT / EN_BANK_LOGO_RELATIVE_PATH

UTILITY_NAVIGATION_ITEMS = (
    ("home", "صفحه اصلی", "/"),
    ("folder", "سناریوهای ذخیره‌شده", "/?view=saved#saved-scenarios"),
)

ICON_SVGS = {
    "home": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 10.5 8-6 8 6"/><path d="M6.5 9.5V20h11V9.5"/><path d="M10 20v-6h4v6"/></svg>',
    "folder": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 6.5h6l2 2h9v10.5h-17z"/><path d="M3.5 9h17"/></svg>',
    "bank": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 9h18L12 4z"/><path d="M5 9v10"/><path d="M9.5 9v10"/><path d="M14.5 9v10"/><path d="M19 9v10"/><path d="M3 19h18"/></svg>',
    "buildings": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V7h7v13"/><path d="M13 20V4h7v16"/><path d="M7 10h1.5M7 14h1.5M16 8h1.5M16 12h1.5M16 16h1.5"/><path d="M2.5 20h19"/></svg>',
    "target": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="13" r="6.5"/><circle cx="11" cy="13" r="3"/><path d="m15.5 8.5 4-4"/><path d="M17 4.5h2.5V7"/></svg>',
}


def icon_svg(name: str) -> str:
    return ICON_SVGS[name]


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


def _logo_data_uri() -> str | None:
    if not EN_BANK_LOGO_PATH.is_file():
        return None
    mime_type = mimetypes.guess_type(EN_BANK_LOGO_PATH.name)[0] or "image/png"
    return f"data:{mime_type};base64,{base64.b64encode(EN_BANK_LOGO_PATH.read_bytes()).decode('ascii')}"


def render_navigation() -> None:
    """Render native page links inside the custom right navigation panel."""
    logo_html = ""
    logo_data_uri = _logo_data_uri()
    if logo_data_uri:
        logo_html = f'<img src="{logo_data_uri}" alt="بانک اقتصاد نوین" />'
    with st.sidebar:
        st.markdown(
            f'<div class="nav-brand"><span class="nav-brand-mark" aria-label="بانک اقتصاد نوین">{logo_html}</span>'
            '<div><strong>سامانه تحلیل حساسیت شعب</strong><small>درجه‌بندی و تحلیل سناریو</small></div></div>',
            unsafe_allow_html=True,
        )
        utility_links = "".join(
            f'<a class="scenario-nav-link" href="{href}" target="_self">{icon_svg(icon)} '
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
                f'target="_self">{icon_svg(item.icon)}'
                f'<span>{html.escape(item.label)}</span></a>'
            )
        st.markdown(f'<nav class="scenario-nav">{"".join(links)}</nav>', unsafe_allow_html=True)
