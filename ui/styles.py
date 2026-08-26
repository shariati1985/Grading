"""Application shell and centralized banking design system."""

from __future__ import annotations

import streamlit as st

from .navigation import render_navigation
from domain.scenario_contracts import ScenarioType


def apply_global_styles(
    *, active_view: str = "home", active_scenario: ScenarioType | None = None
) -> None:
    """Render custom navigation and apply the complete responsive visual shell."""
    st.markdown(
        """
        <style>
        :root {
            --primary-navy: #14233f;
            --en-purple-900: #4C1D6F;
            --en-purple-800: #572779;
            --en-purple-700: #65328A;
            --en-purple-600: #75439A;
            --en-purple-100: #F0E8F5;
            --en-purple-50: #F8F4FA;
            --en-navy-900: #17243B;
            --en-navy-800: #22324D;
            --en-navy-700: #344765;
            --en-navy-100: #E9EEF5;
            --en-navy-50: #F5F7FA;
            --neutral-900: #202838;
            --neutral-700: #4F5B70;
            --neutral-600: #687386;
            --neutral-300: #D8DDE6;
            --neutral-200: #E7EAF0;
            --neutral-100: #F2F4F7;
            --neutral-50: #F8F9FB;
            --brand-purple: var(--en-purple-700);
            --brand-purple-dark: var(--en-purple-900);
            --brand-purple-light: var(--en-purple-100);
            --app-bg: #FFFFFF;
            --surface: #FFFFFF;
            --secondary-bg: #f6f7fa;
            --primary: var(--primary-navy);
            --secondary-navy: #21385e;
            --accent: var(--brand-purple);
            --accent-dark: var(--brand-purple-dark);
            --accent-soft: var(--brand-purple-light);
            --success: #16835B;
            --success-bg: #E9F7F1;
            --danger: #C43D4B;
            --danger-bg: #FDEDEF;
            --warning: #B7791F;
            --warning-bg: #FFF6E5;
            --text-primary: #14233f;
            --text-secondary: #667085;
            --muted: var(--text-secondary);
            --border: #dfe4ec;
            --radius: 8px;
            --radius-lg: 12px;
            --shadow: 0 8px 22px rgba(20, 35, 63, 0.08);
            --shadow-soft: 0 3px 10px rgba(20, 35, 63, 0.06);
            --app-font-fa: "Vazirmatn", "IRANSansX", "IRANSans", "Segoe UI", Tahoma, Arial, sans-serif;
            --font: var(--app-font-fa);
            --nav-width: 292px;
            --streamlit-header-offset: 3.75rem;
        }

        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] *,
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] *,
        [data-testid="stMarkdownContainer"],
        [data-testid="stMarkdownContainer"] *,
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] *,
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] *,
        button,
        button *,
        input,
        textarea,
        select {
            font-family: var(--font) !important;
            letter-spacing: normal !important;
        }
        /* Preserve Streamlit's icon-ligature font so internal glyph names can
           never fall back to ordinary clipped text. */
        [data-testid="stIconMaterial"] { font-family: "Material Symbols Rounded", sans-serif !important; }
        html, body, [data-testid="stAppViewContainer"] {
            direction: rtl;
            text-align: right;
            color: var(--primary);
            background: var(--app-bg);
            font-size: 15px;
            line-height: 1.75;
            overflow-x: hidden;
        }
        [data-testid="stAppViewContainer"] > .main { min-width: 0; }
        [data-testid="stMainBlockContainer"],
        .block-container {
            width: min(100%, 1320px);
            max-width: 1320px;
            margin-inline: auto;
            padding: calc(var(--streamlit-header-offset) + .75rem) 2rem 3rem !important;
            overflow-x: clip;
        }
        a, a:hover, a:focus, a:focus-visible, a:active, a:visited,
        [data-testid="stMarkdownContainer"] a,
        [data-testid="stMarkdownContainer"] a:hover,
        [data-testid="stMarkdownContainer"] a:focus,
        [data-testid="stMarkdownContainer"] a:active,
        [data-testid="stMarkdownContainer"] a:visited {
            text-decoration: none !important;
        }
        h1, h2, h3, p, label, .stMarkdown { text-align: right; }
        h1 { font-size: 30px !important; line-height: 1.5 !important; font-weight: 600 !important;
            color: var(--primary); margin-bottom: .2rem !important; overflow-wrap: normal; }
        h2 { font-size: 22px !important; line-height: 1.6 !important; font-weight: 600 !important;
            color: var(--primary); }
        h3 { font-size: 19px !important; line-height: 1.65 !important; font-weight: 600 !important;
            color: var(--primary); }
        p, label, [data-testid="stCaptionContainer"] { font-size: 15px; line-height: 1.75; }
        .page-subtitle { color: var(--muted); font-size: 15px; line-height: 1.9;
            margin: -.15rem 0 .9rem; max-width: 920px; }
        .bank-hero { display: none; }
        .bank-hero h1 { margin: 0 !important; color: #fff !important; }
        .bank-hero p { margin: 3px 0 0; color: #D9E2EC; }
        .bank-logo-slot, .nav-brand-mark:empty { display: none; }
        .bank-logo-slot:has(img), .nav-brand-mark:has(img) { display: inline-flex; }
        .bank-logo-slot { flex: 0 0 68px; width: 68px; height: 54px; align-items: center; justify-content: center;
            padding: 6px; background: #fff; border-radius: 9px; }
        .bank-logo-slot img { max-width: 100%; max-height: 100%; object-fit: contain; }

        .multi-branch-page { container-type: inline-size; }
        .multi-branch-workflow { margin: 18px 0 24px; overflow-x: auto; }
        .multi-branch-workflow ol { display: grid; grid-template-columns: repeat(5, minmax(150px, 1fr));
            gap: 8px; min-width: 780px; padding: 0; margin: 0; list-style: none; }
        .multi-branch-workflow li { display: flex; align-items: center; gap: 9px; min-height: 54px;
            padding: 9px 12px; color: var(--muted); background: var(--neutral-50);
            border: 1px solid var(--border); border-radius: var(--radius); }
        .multi-branch-workflow li b { display: inline-flex; align-items: center; justify-content: center;
            width: 28px; height: 28px; flex: 0 0 28px; border-radius: 999px; background: var(--neutral-200); }
        .multi-branch-workflow li.active { color: var(--accent); background: var(--accent-soft); border-color: var(--accent); }
        .multi-branch-workflow li.active b { color: #fff; background: var(--accent); }
        .multi-branch-workflow li.completed b { color: #fff; background: var(--success); }
        .multi-branch-stage-header { display: flex; align-items: center; gap: 13px; margin: 8px 0 18px; }
        .multi-branch-stage-header > span { display: inline-flex; align-items: center; justify-content: center;
            width: 48px; height: 48px; flex: 0 0 48px; color: var(--accent); background: var(--accent-soft); border-radius: var(--radius); }
        .multi-branch-stage-header svg { width: 25px; height: 25px; fill: none; stroke: currentColor;
            stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
        .multi-branch-stage-header h2, .multi-branch-stage-header p { margin: 0 !important; }
        .multi-branch-stage-header p { color: var(--muted); }
        .multi-branch-empty { padding: 20px; margin: 10px 0; color: var(--muted); text-align: center;
            background: var(--neutral-50); border: 1px dashed var(--border); border-radius: var(--radius); }
        .multi-network-summary, .multi-primary-result { margin: 24px 0 10px; font-family: var(--font) !important; }
        .multi-network-summary h2, .multi-primary-result h2 { margin: 0 !important; color: var(--primary);
            font-size: 20px !important; font-weight: 800 !important; }
        .multi-primary-result { padding: 15px 18px; background: var(--accent-soft);
            border: 1px solid #e1d5ea; border-right: 4px solid var(--accent); border-radius: var(--radius); }
        .multi-primary-result header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .multi-primary-result p { margin: 2px 0 0; color: var(--muted); font-size: 13px; }
        .multi-branch-page [data-testid="stDataFrame"] { direction: rtl; border: 1px solid var(--border);
            border-radius: var(--radius); box-shadow: var(--shadow-soft); overflow: hidden; }
        [data-multi-branch-results="true"] { display: block; direction: rtl; container-type: inline-size; margin: 8px 0 0; font-family: var(--font) !important; }
        .multi-branch-page [data-testid="stTabs"] [role="tablist"] { position: static; top: auto; z-index: auto; margin: 10px 0 14px; }
        .multi-branch-page [data-testid="stTabs"] [role="tabpanel"] { padding-top: 0; }
        [data-multi-branch-results="true"] .multi-results-header { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin: 4px 0 12px; }
        [data-multi-branch-results="true"] .multi-results-header h1 { margin: 0 !important; color: var(--en-navy-900); font-size: 27px !important; line-height: 1.55 !important; font-weight: 800 !important; }
        [data-multi-branch-results="true"] .multi-results-header p { margin: 2px 0 0; color: var(--neutral-700); font-size: 14px; line-height: 1.8; }
        [data-multi-branch-results="true"] .multi-results-metadata { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 10px; margin: 0 0 16px; }
        [data-multi-branch-results="true"] .multi-results-metadata article { min-width: 0; padding: 11px 13px; background: #fff; border: 1px solid var(--neutral-200); border-radius: 12px; box-shadow: var(--shadow-soft); }
        [data-multi-branch-results="true"] .multi-results-metadata span { display: block; color: var(--neutral-600); font-size: 11px; line-height: 1.7; font-weight: 800; }
        [data-multi-branch-results="true"] .multi-results-metadata strong { display: block; color: var(--en-navy-900); font-size: 13px; line-height: 1.75; font-weight: 900; overflow-wrap: break-word; }
        [data-multi-branch-results="true"] bdi { unicode-bidi: isolate; direction: rtl; }
        [data-multi-branch-results="true"] .managerial-conclusion { margin: 14px 0; padding: 16px 18px; background: #fff; border: 1px solid var(--neutral-200); border-right: 4px solid var(--accent); border-radius: 12px; box-shadow: var(--shadow-soft); }
        [data-multi-branch-results="true"] .managerial-conclusion.success { border-right-color: var(--success); }
        [data-multi-branch-results="true"] .managerial-conclusion.danger { border-right-color: var(--danger); }
        [data-multi-branch-results="true"] .managerial-conclusion h2 { margin: 0 0 6px !important; color: var(--en-navy-900); font-size: 18px !important; font-weight: 900 !important; }
        [data-multi-branch-results="true"] .managerial-conclusion p { margin: 0; color: var(--neutral-700); font-size: 14px; line-height: 1.9; }
        [data-multi-branch-results="true"] .managerial-conclusion ul { display: flex; flex-wrap: wrap; gap: 7px; margin: 10px 0 0; padding: 0; list-style: none; }
        [data-multi-branch-results="true"] .managerial-conclusion li { padding: 5px 9px; background: var(--neutral-50); border: 1px solid var(--neutral-200); border-radius: 999px; color: var(--neutral-700); font-size: 12px; font-weight: 800; }
        [data-multi-branch-results="true"] .multi-kpi-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 10px; margin: 12px 0 16px; }
        [data-multi-branch-results="true"] .multi-kpi { min-width: 0; min-height: 112px; display: grid; align-content: center; gap: 5px; padding: 14px 16px; background: #fff; border: 1px solid var(--neutral-200); border-radius: 12px; box-shadow: var(--shadow-soft); }
        [data-multi-branch-results="true"] .multi-kpi span { color: var(--neutral-600); font-size: 12px; font-weight: 800; }
        [data-multi-branch-results="true"] .multi-kpi strong { color: var(--en-navy-900); font-size: 23px; line-height: 1.5; font-weight: 900; overflow-wrap: anywhere; }
        [data-multi-branch-results="true"] .multi-kpi small { color: var(--neutral-700); font-size: 11px; font-weight: 700; }
        [data-multi-branch-results="true"] .multi-kpi.success strong { color: var(--success); }
        [data-multi-branch-results="true"] .multi-kpi.danger strong { color: var(--danger); }
        [data-multi-branch-results="true"] .multi-empty-state { min-height: 92px; display: grid; place-items: center; padding: 18px; color: var(--neutral-700); background: var(--neutral-50); border: 1px dashed var(--neutral-300); border-radius: 12px; font-weight: 800; text-align: center; }
        [data-multi-branch-results="true"] .multi-movers-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; margin: 16px 0; }
        [data-multi-branch-results="true"] .multi-mover-panel { min-width: 0; padding: 14px; background: #fff; border: 1px solid var(--neutral-200); border-radius: 12px; box-shadow: var(--shadow-soft); }
        [data-multi-branch-results="true"] .multi-mover-panel h3 { margin: 0 0 10px !important; color: var(--en-navy-900); font-size: 16px !important; font-weight: 900 !important; }
        [data-multi-branch-results="true"] .multi-mover-row { padding: 10px 0; border-top: 1px solid #eef1f5; }
        [data-multi-branch-results="true"] .multi-mover-row:first-of-type { border-top: 0; }
        [data-multi-branch-results="true"] .multi-mover-row header { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
        [data-multi-branch-results="true"] .multi-mover-row strong { color: var(--en-navy-900); font-size: 13px; font-weight: 900; overflow-wrap: anywhere; }
        [data-multi-branch-results="true"] .multi-mover-row small { color: var(--neutral-600); font-size: 11px; font-weight: 800; white-space: nowrap; }
        [data-multi-branch-results="true"] .multi-mover-row div { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
        [data-multi-branch-results="true"] .multi-mover-row span, [data-multi-branch-results="true"] .multi-mover-row b { padding: 4px 7px; background: var(--neutral-50); border-radius: 999px; color: var(--neutral-700); font-size: 11px; font-weight: 800; }
        [data-multi-branch-results="true"] .multi-mover-row.success b { color: var(--success); background: var(--success-bg); }
        [data-multi-branch-results="true"] .multi-mover-row.danger b { color: var(--danger); background: var(--danger-bg); }
        [data-multi-branch-results="true"] .multi-primary-panel { margin: 18px 0 10px; padding: 15px 18px; background: var(--en-purple-50); border: 1px solid #e1d5ea; border-right: 4px solid var(--accent); border-radius: 12px; }
        [data-multi-branch-results="true"] .multi-primary-panel h2 { margin: 0 !important; color: var(--en-navy-900); font-size: 19px !important; font-weight: 900 !important; }
        [data-multi-branch-results="true"] .multi-primary-panel p { margin: 2px 0 0; color: var(--neutral-700); font-size: 13px; }
        [data-multi-branch-results="true"] .multi-primary-panel > div { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 8px; margin-top: 12px; }
        [data-multi-branch-results="true"] .multi-primary-panel span { min-width: 0; padding: 8px 10px; background: #fff; border: 1px solid var(--neutral-200); border-radius: 10px; }
        [data-multi-branch-results="true"] .multi-primary-panel small { display: block; color: var(--neutral-600); font-size: 11px; font-weight: 800; }
        [data-multi-branch-results="true"] .multi-primary-panel b { display: block; color: var(--en-navy-900); font-size: 13px; line-height: 1.7; font-weight: 900; }
        @container (max-width: 980px) {
            [data-multi-branch-results="true"] .multi-kpi-grid,
            [data-multi-branch-results="true"] .multi-results-metadata,
            [data-multi-branch-results="true"] .multi-primary-panel > div { grid-template-columns: repeat(2,minmax(0,1fr)); }
            [data-multi-branch-results="true"] .multi-movers-grid { grid-template-columns: minmax(0,1fr); }
        }
        @container (max-width: 620px) {
            [data-multi-branch-results="true"] .multi-results-header { align-items: flex-start; flex-direction: column; }
            [data-multi-branch-results="true"] .multi-kpi-grid,
            [data-multi-branch-results="true"] .multi-results-metadata,
            [data-multi-branch-results="true"] .multi-primary-panel > div { grid-template-columns: minmax(0,1fr); }
        }

        /* Keep Streamlit's native sidebar layout so its reserved space remains
           correct under browser zoom and viewport resizing. */
        [data-testid="stSidebar"] {
            width: var(--nav-width) !important;
            min-width: var(--nav-width) !important;
            background: var(--surface);
            border-right: 1px solid var(--border);
            box-shadow: 4px 0 22px rgba(20, 35, 63, .06);
        }
        [data-testid="stSidebar"] > div { width: var(--nav-width) !important; }
        [data-testid="stSidebar"] * { direction: rtl; text-align: right; }
        [data-testid="stSidebarNav"] { display: none !important; }
        [data-testid="stSidebarUserContent"] { box-sizing: border-box; min-height: calc(100vh - 22px); max-height: calc(100vh - 22px); overflow-y: auto; padding: 22px 14px 24px; display: flex; flex-direction: column; }
        [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {
            min-height: calc(100vh - 112px);
            display: flex;
            flex-direction: column;
        }
        [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(.nav-user-card) {
            margin-top: auto;
        }
        @media (min-width: 801px) {
            [data-testid="stSidebarCollapseButton"] { display: none !important; }
        }
        .scenario-nav { display: grid; gap: 9px; }
        .utility-nav { display: grid; gap: 9px; padding-bottom: 14px; margin-bottom: 14px; }
        .scenario-nav { flex: 1 1 auto; }
        .scenario-nav-link {
            display: flex;
            direction: rtl;
            align-items: center;
            flex-direction: row;
            justify-content: flex-start;
            gap: 13px;
            min-height: 56px;
            margin: 0;
            padding: 0 18px;
            border-radius: var(--radius);
            color: var(--primary);
            text-decoration: none !important;
            font-size: 15px;
            font-weight: 600;
            white-space: normal;
            overflow-wrap: anywhere;
            border: 1px solid transparent;
            position: relative;
            transition: background .15s ease, color .15s ease, border-color .15s ease, box-shadow .15s ease;
        }
        [data-testid="stSidebar"] .scenario-nav-link,
        [data-testid="stSidebar"] .scenario-nav-link:visited {
            color: var(--primary) !important;
        }
        .scenario-nav-link svg {
            flex: 0 0 22px;
            flex-shrink: 0;
            width: 22px;
            height: 22px;
            fill: none;
            stroke: currentColor;
            stroke-width: 1.8;
            stroke-linecap: round;
            stroke-linejoin: round;
        }
        .scenario-nav-link:hover {
            background: var(--accent-soft);
            color: var(--accent) !important;
            text-decoration: none !important;
        }
        .scenario-nav-link:focus-visible {
            outline: 2px solid var(--accent);
            outline-offset: 2px;
            text-decoration: none !important;
        }
        .scenario-nav-link.active {
            color: var(--accent) !important;
            background: var(--accent-soft);
            font-weight: 600;
            box-shadow: inset -4px 0 0 var(--accent);
        }
        .nav-brand { display: flex; direction: rtl; flex-direction: column; align-items: stretch; gap: 11px;
            padding: 3px 9px 28px; margin-bottom: 20px; }
        .nav-brand-mark { direction: ltr; display: block; width: min(100%, 226px); min-height: 0;
            border-radius: 0; color: transparent; background: transparent; overflow: hidden; }
        .nav-brand-mark:empty { display: none; }
        .nav-brand-mark img { display: block; width: 100%; height: auto; max-height: 68px; object-fit: contain; object-position: right center; }
        .nav-brand strong { display: block; font-size: 17px; line-height: 1.8; font-weight: 700; color: var(--primary); }
        .nav-brand small { display: block; font-size: 13px; line-height: 1.7; color: var(--muted); margin-top: 2px; }
        .nav-user-card { margin-top: auto; margin-bottom: 0; min-height: 76px; display: flex; direction: rtl; align-items: center;
            gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid var(--border); border-radius: var(--radius);
            box-shadow: var(--shadow-soft); font-family: var(--font) !important; }
        .nav-user-toggle { flex: 0 0 18px; color: var(--primary); font-size: 18px; text-align: center; }
        .nav-user-text { min-width: 0; flex: 1 1 auto; display: grid; gap: 2px; text-align: right; }
        .nav-user-text strong { color: var(--primary); font-size: 14px; line-height: 1.6; font-weight: 700; overflow-wrap: anywhere; }
        .nav-user-text small { color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
        .nav-user-avatar { flex: 0 0 42px; width: 42px; height: 42px; display: inline-flex; align-items: center; justify-content: center;
            color: var(--accent); background: var(--accent-soft); border-radius: 999px; }
        .nav-user-avatar svg { width: 24px; height: 24px; fill: none; stroke: currentColor; stroke-width: 1.8;
            stroke-linecap: round; stroke-linejoin: round; }

        [data-testid="stMetric"], [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
        }
        [data-testid="stMetric"] { padding: 16px 18px; min-height: 108px; overflow: visible; }
        [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {
            color: var(--muted);
            font-size: 13px !important;
            line-height: 1.6 !important;
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
        }
        [data-testid="stMetricValue"] {
            color: var(--primary);
            font-size: 27px !important;
            font-weight: 600 !important;
            line-height: 1.45;
            white-space: normal;
            overflow: visible;
            overflow-wrap: anywhere;
            unicode-bidi: plaintext;
        }
        [data-testid="stMetricDelta"] { font-size: 13px; }
        .kpi-panel { background: var(--surface); border: 1px solid var(--border);
            border-radius: var(--radius); box-shadow: var(--shadow); padding: 17px 18px; min-height: 148px; }
        .kpi-panel-title { color: var(--accent); font-size: 15px; font-weight: 600;
            padding-bottom: 9px; margin-bottom: 11px; border-bottom: 1px solid var(--border); }
        .kpi-panel-grid { display: grid; grid-template-columns: repeat(var(--kpi-count), minmax(0, 1fr)); gap: 14px; }
        .kpi-panel-item { min-width: 0; }
        .kpi-panel-label { color: var(--muted); font-size: 13px; line-height: 1.55; white-space: normal; }
        .kpi-panel-value { direction: ltr; text-align: right; unicode-bidi: plaintext; color: var(--primary);
            font-size: 23px; line-height: 1.5; font-weight: 600; overflow-wrap: anywhere; }
        .kpi-panel-delta { direction: rtl; font-size: 12px; line-height: 1.5; margin-top: 2px; }
        .kpi-panel-delta.success { color: var(--success); }
        .kpi-panel-delta.danger { color: var(--danger); }
        .kpi-panel-delta.neutral { color: var(--muted); }

        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 6px; padding: 5px; overflow-x: auto; background: #ECEFF5; border-radius: 11px;
        }
        [data-testid="stTabs"] [data-baseweb="tab"] {
            min-height: 42px; padding-inline: 18px; border-radius: 8px; white-space: nowrap;
            color: var(--muted);
        }
        [data-testid="stTabs"] [aria-selected="true"] {
            background: var(--surface); color: var(--primary); box-shadow: 0 1px 4px rgba(16,24,40,.08);
        }
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
            direction: rtl; max-width: 100%; overflow: auto; background: var(--surface);
            border: 1px solid var(--border); border-radius: 11px;
        }
        [data-testid="stDataFrame"] *, [data-testid="stDataEditor"] * {
            font-family: var(--font) !important; font-size: 14px;
        }
        [data-testid="stDataFrame"] canvas, [data-testid="stDataEditor"] canvas {
            direction: ltr; font-family: var(--font) !important;
        }
        [data-testid="stBaseButton-primary"] {
            min-width: 112px; min-height: 44px; width: 100% !important; padding-inline: 28px !important;
            color: #fff !important; background: var(--secondary-navy) !important;
            border-color: var(--accent) !important; border-radius: 10px; font-weight: 600;
        }
        [data-testid="stBaseButton-primary"]:hover { background: var(--accent) !important; border-color: var(--accent) !important; }
        [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button {
            min-width: 112px; min-height: 44px; width: 100% !important; max-width: 100%; border-radius: 10px;
            white-space: normal; overflow-wrap: anywhere;
        }
        [data-testid="stTextInput"] input, [data-testid="stSelectbox"] > div,
        [data-testid="stMultiSelect"] > div { border-radius: 9px; }
        [data-testid="stTextInput"] input,
        [data-testid="stSelectbox"] [data-baseweb="select"],
        [data-testid="stSelectbox"] [data-baseweb="select"] *,
        [data-testid="stSelectbox"] [role="combobox"],
        [data-testid="stMultiSelect"] [data-baseweb="select"],
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] * {
            direction: rtl !important;
            text-align: right !important;
            font-family: var(--font) !important;
        }
        [data-testid="stSelectbox"] [data-baseweb="select"] {
            min-height: 50px; background: #fbf8fd !important; border: 1px solid #dfe4ec !important;
            border-radius: 11px !important; box-shadow: var(--shadow-soft); transition: border-color .15s ease, box-shadow .15s ease;
        }
        [data-testid="stSelectbox"] .react-aria-ComboBox [role="group"] {
            min-height: 50px; display: flex; align-items: center; background: #fbf8fd !important; border: 1px solid #dfe4ec !important;
            border-radius: 11px !important; box-shadow: var(--shadow-soft); transition: border-color .15s ease, box-shadow .15s ease;
        }
        [data-testid="stSelectbox"] .react-aria-ComboBox input {
            min-height: 48px; background: transparent !important; border: 0 !important; color: var(--primary) !important;
            font-family: var(--font) !important; font-weight: 500 !important; direction: rtl !important; text-align: right !important;
        }
        [data-testid="stSelectbox"] [data-baseweb="select"]:hover { border-color: #c7a7dd !important; }
        [data-testid="stSelectbox"] .react-aria-ComboBox [role="group"]:hover { border-color: #c7a7dd !important; }
        [data-testid="stSelectbox"] [data-baseweb="select"]:focus-within {
            border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(108,47,143,.12);
        }
        [data-testid="stSelectbox"] .react-aria-ComboBox [role="group"]:focus-within {
            border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(108,47,143,.12);
        }
        [data-testid="stSelectbox"] [data-baseweb="select"]::before {
            content: "🏦"; display: inline-flex; align-items: center; justify-content: center;
            width: 28px; height: 28px; margin-inline: 10px 6px; border-radius: 8px;
            background: var(--accent-soft); color: var(--accent); font-size: 15px; flex: 0 0 28px;
        }
        [data-testid="stSelectbox"] .react-aria-ComboBox [role="group"]::before {
            content: "🏦"; display: inline-flex; align-items: center; justify-content: center;
            width: 28px; height: 28px; margin-inline: 10px 6px; border-radius: 8px;
            background: var(--accent-soft); color: var(--accent); font-size: 15px; flex: 0 0 28px;
        }
        [data-testid="stSelectbox"] svg { margin-inline-start: auto; margin-inline-end: 0; color: var(--accent); }
        [data-baseweb="popover"], [data-baseweb="popover"] *,
        [data-rac][role="listbox"], [data-rac][role="listbox"] *,
        [role="listbox"], [role="listbox"] * {
            direction: rtl !important; text-align: right !important; font-family: var(--font) !important;
        }
        [role="option"] { min-height: 42px !important; padding-block: 9px !important; line-height: 1.8 !important; }
        [role="option"]:hover { background: var(--accent-soft) !important; }
        [aria-selected="true"][role="option"] { background: #f4edf8 !important; color: var(--accent) !important; font-weight: 700 !important; }
        input, [data-testid="stMetricValue"], [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
            font-variant-numeric: tabular-nums;
        }
        .stPlotlyChart { direction: ltr; background: var(--surface); border: 1px solid var(--border);
            border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow); }
        .branch-identity { padding: 12px 16px; background: var(--surface); border: 1px solid var(--border);
            border-right: 4px solid var(--accent); border-radius: 10px; margin-bottom: 10px; }
        [data-testid="stToolbar"], #MainMenu, footer, [data-testid="stStatusWidget"],
        [data-testid="stDecoration"] { display: none !important; }

        @media (max-width: 1100px) {
            [data-testid="stMainBlockContainer"], .block-container { padding-inline: 1rem !important; }
            [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 12px; }
            [data-testid="column"] { min-width: min(100%, 300px) !important; flex: 1 1 300px !important; }
            .kpi-panel-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 800px) {
            [data-testid="stMainBlockContainer"], .block-container {
                padding: calc(var(--streamlit-header-offset) + .75rem) .7rem 2rem !important;
            }
            h1 { font-size: 25px !important; }
            h2 { font-size: 20px !important; }
            [data-testid="column"] { min-width: 100% !important; }
            .home-page-header h1 { font-size: 24px !important; overflow-wrap: anywhere; }
            .home-page-header p { font-size: 14px; }
            .home-decision-panel { min-height: 260px; padding: 28px 18px; }
            .home-decision-panel h2 { font-size: 22px !important; }
            .home-decision-panel p { font-size: 14px; }
            .scenario-card-grid,
            .home-overview-grid { grid-template-columns: minmax(0, 1fr) !important; gap: 14px; }
            .scenario-card { min-height: 206px; }
        }
        .home-page-header { position: relative; z-index: 1; padding: 4px 0 18px; text-align: center; }
        .home-page-header h1 { margin: 10px 0 2px !important; text-align: center; font-size: 31px !important; font-weight: 800 !important; color: var(--primary); }
        .home-page-header p { margin: 0 auto; text-align: center; color: var(--text-secondary); font-size: 16px; max-width: 760px; }
        .home-user-chip { display: inline-flex; align-items: center; gap: 10px; direction: rtl; color: var(--primary);
            position: relative; z-index: 2; font-family: var(--font) !important; }
        .home-user-chip b { display: block; font-size: 14px; }
        .home-user-chip small { display: block; color: var(--text-secondary); font-size: 12px; }
        .home-user-icon { width: 36px; height: 36px; border-radius: 999px; background: var(--brand-purple-light); border: 1px solid #d9d0e6; position: relative; }
        .home-user-icon::before { content: ""; position: absolute; inset: 9px 11px 15px; border-radius: 999px; background: #8d98ad; }
        .home-user-icon::after { content: ""; position: absolute; left: 9px; right: 9px; bottom: 7px; height: 9px; border-radius: 999px 999px 5px 5px; background: #8d98ad; }
        .home-decision-panel { position: relative; overflow: hidden; min-height: 214px; margin: 7px 0 26px; padding: 34px 48px;
            display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;
            color: #fff; background: #14264d; border-radius: var(--radius-lg); box-shadow: 0 12px 26px rgba(20,35,63,.18); }
        .home-decision-panel h2 { margin: 0 0 13px !important; color: #fff !important; text-align: center; font-size: 24px !important; font-weight: 800 !important; }
        .home-decision-panel p { max-width: 690px; margin: 0 0 22px; color: #eef2f8; text-align: center; line-height: 2; }
        .decision-panel-pattern::before, .decision-panel-pattern::after { content: ""; position: absolute; width: 110px; height: 260px; top: -24px;
            background: rgba(108,47,143,.38); transform: skewX(-32deg); border-radius: 12px; }
        .decision-panel-pattern::before { right: 74px; }
        .decision-panel-pattern::after { left: 60px; }
        .decision-panel-action { position: relative; z-index: 1; min-height: 46px; display: inline-flex; direction: rtl; flex-direction: row; align-items: center; justify-content: flex-start; gap: 12px;
            padding: 0 26px; color: #fff !important; background: var(--brand-purple); border-radius: var(--radius);
            font-weight: 700; box-shadow: var(--shadow-soft); }
        .decision-panel-action:hover, .decision-panel-action:focus-visible { background: var(--brand-purple-dark); color: #fff !important; outline: 2px solid rgba(255,255,255,.55); outline-offset: 2px; }
        .home-section-title { margin: 18px 0 12px !important; text-align: right; font-size: 22px !important; font-weight: 800 !important; color: var(--primary); }
        .scenario-card-grid { container-type: inline-size; display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 22px; margin-bottom: 30px; }
        .scenario-card { min-width: 0; min-height: 214px; display: flex; flex-direction: column; align-items: center;
            padding: 20px 22px 0; text-align: center; color: var(--primary); text-decoration: none !important;
            background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
            box-shadow: var(--shadow-soft); transition: transform .15s ease, border-color .15s ease, box-shadow .15s ease; }
        .scenario-card:hover, .scenario-card:focus-visible { color: var(--primary); border-color: #cfc3dc;
            box-shadow: 0 10px 24px rgba(20,35,63,.12); transform: translateY(-2px); outline: none; text-decoration: none !important; }
        .scenario-card:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
        .scenario-card-icon { width: 76px; height: 76px; display: inline-flex; align-items: center; justify-content: center;
            color: var(--accent); background: var(--accent-soft); border-radius: 999px; }
        .scenario-card-icon svg { width: 42px; height: 42px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
        .scenario-card h3 { margin: 14px 0 8px; text-align: center; font-size: 17px !important; font-weight: 800 !important; text-decoration: none !important; }
        .scenario-card p { color: var(--text-secondary); text-align: center; line-height: 1.9; margin: 0 0 16px; flex: 1; font-size: 14px; }
        .scenario-card-start { align-self: stretch; min-height: 44px; display: inline-flex; direction: rtl; flex-direction: row; justify-content: center; align-items: center; gap: 12px;
            padding-inline: 12px; color: var(--accent); background: transparent; border-top: 1px solid var(--border); font-weight: 700; font-size: 13px; }
        .scenario-card-start b { font-size: 20px; line-height: 1; }
        .home-overview-grid { container-type: inline-size; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 22px; margin: 0 0 26px; }
        .home-overview-grid article { min-height: 112px; display: flex; direction: rtl; flex-direction: row; align-items: center; justify-content: flex-start; gap: 18px;
            padding: 18px 22px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
            box-shadow: var(--shadow-soft); text-align: right; font-family: var(--font) !important; }
        .overview-content { min-width: 0; flex: 1 1 auto; display: flex; flex-direction: column; align-items: flex-start;
            justify-content: center; gap: 3px; direction: rtl; text-align: right; font-family: var(--font) !important; line-height: 1.7; }
        .home-overview-grid .overview-value { display: block; width: 100%; color: var(--primary); font-family: var(--font) !important;
            font-size: 26px; line-height: 1.7; font-weight: 700; text-align: right; }
        .home-overview-grid .overview-label { display: block; width: 100%; color: var(--text-secondary); font-family: var(--font) !important;
            font-size: 13px; line-height: 1.7; font-weight: 600; text-align: right; }
        .overview-icon { flex: 0 0 58px; width: 58px; height: 58px; display: inline-flex; align-items: center; justify-content: center;
            color: var(--accent); background: var(--accent-soft); border: 1px solid #e1d5ea; border-radius: 999px; font-family: var(--font) !important; }
        .overview-icon svg { width: 34px; height: 34px; flex-shrink: 0; fill: none; stroke: currentColor; stroke-width: 1.75;
            stroke-linecap: round; stroke-linejoin: round; }
        @container (max-width: 760px) { .home-overview-grid { grid-template-columns: minmax(0, 1fr); } }
        @container (max-width: 1080px) { .scenario-card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
        @container (max-width: 620px) { .scenario-card-grid { grid-template-columns: minmax(0, 1fr); } }
        [data-testid="stSidebar"] a.scenario-nav-link,
        [data-testid="stSidebar"] a.scenario-nav-link:link,
        [data-testid="stSidebar"] a.scenario-nav-link:visited,
        [data-testid="stSidebar"] a.scenario-nav-link:hover,
        [data-testid="stSidebar"] a.scenario-nav-link:focus,
        [data-testid="stSidebar"] a.scenario-nav-link:active {
            text-decoration: none !important;
        }
        [data-testid="stSidebar"] a.scenario-nav-link,
        [data-testid="stSidebar"] a.scenario-nav-link:link,
        [data-testid="stSidebar"] a.scenario-nav-link:visited {
            color: var(--primary) !important;
        }
        [data-testid="stSidebar"] a.scenario-nav-link:hover,
        [data-testid="stSidebar"] a.scenario-nav-link:focus,
        [data-testid="stSidebar"] a.scenario-nav-link.active {
            color: var(--accent) !important;
        }
        @media (max-width: 800px) {
            .scenario-card-grid,
            .home-overview-grid { grid-template-columns: minmax(0, 1fr) !important; }
            .home-decision-panel { padding-inline: 18px; }
        }
        .numeric-ltr { direction: ltr; unicode-bidi: isolate; text-align: right; font-variant-numeric: tabular-nums;
            max-width: 100%; overflow: hidden; word-break: keep-all; text-overflow: ellipsis; white-space: nowrap; }
        .numeric-fa { direction: rtl; unicode-bidi: isolate; text-align: right; font-variant-numeric: tabular-nums;
            font-family: var(--font) !important; }
        .value-comparison-card { container-type: inline-size; display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
        .value-comparison-item { min-width: 0; min-height: 104px; padding: 14px; border: 1px solid var(--border);
            border-radius: 8px; background: #F8FAFC; box-shadow: var(--shadow-soft); }
        .value-comparison-item.scenario { border-right-color: var(--accent); background: #fbf8fd; }
        .value-comparison-item.success strong { color: var(--success); }
        .value-comparison-item.danger strong { color: var(--danger); }
        .value-comparison-item span { display: block; color: var(--muted); font-size: 13px; }
        .value-comparison-item strong { display: block; margin-top: 5px; color: var(--primary);
            font-size: clamp(15px, 2.2cqi, 22px); line-height: 1.5; overflow-wrap: anywhere; }
        @container (max-width: 760px) { .value-comparison-card { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
        @container (max-width: 420px) { .value-comparison-card { grid-template-columns: minmax(0, 1fr); } }
        .comparison-strip-header { display: flex; justify-content: space-between; align-items: center;
            gap: 12px; margin: 14px 0 0; padding: 16px 18px; color: #fff; background: var(--primary);
            border-radius: var(--radius) var(--radius) 0 0; }
        .comparison-strip-header strong { display: block; color: #fff; font-size: 17px; }
        .comparison-strip-header small { display: block; color: #D9E2EC; margin-top: 2px; }
        .comparison-strip-header span { padding: 4px 10px; color: #fff; background: rgba(255,255,255,.12);
            border-radius: 999px; font-size: 12px; }
        .comparison-strip { container-type: inline-size; display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; padding: 1px; margin-bottom: 20px;
            background: var(--border); border-radius: 0 0 var(--radius) var(--radius); box-shadow: var(--shadow); overflow: hidden; }
        .comparison-strip-item { min-width: 0; padding: 15px 16px; background: var(--surface); border: 0; }
        .comparison-strip-item header { display: flex; direction: rtl; align-items: center; gap: 8px; margin-bottom: 12px; }
        .summary-metric-icon { flex: 0 0 34px; width: 34px; height: 34px; display: inline-flex; align-items: center; justify-content: center;
            color: var(--accent); background: var(--accent-soft); border-radius: 9px; }
        .summary-metric-icon svg { width: 21px; height: 21px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
        .comparison-strip-item.success p { color: var(--success); background: var(--success-bg); }
        .comparison-strip-item.danger p { color: var(--danger); background: var(--danger-bg); }
        .comparison-strip-item h3 { margin: 0 !important; font-size: 15px !important; }
        .comparison-values { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
        .comparison-values div { min-width: 0; padding: 7px 8px; background: #F8FAFC; border-radius: 8px; }
        .comparison-values span { display: block; color: var(--muted); font-size: 11px; }
        .comparison-values strong { display: block; font-size: 18px; }
        .comparison-strip-item p { display: inline-flex; align-items: center; gap: 7px; margin: 10px 0 0; padding: 7px 10px; color: var(--muted); background: var(--secondary-bg); border-radius: 999px; font-size: 12px; font-weight: 700; }
        .comparison-strip-item p span { display: inline; font-size: 12px; font-weight: 700; }
        @container (max-width: 700px) { .comparison-strip { grid-template-columns: minmax(0, 1fr); } }
        .indicator-result-grid { container-type: inline-size; display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }
        .indicator-result-card { min-width: 0; padding: 14px; background: var(--surface);
            border: 1px solid var(--border); border-right: 4px solid #98A2B3; border-radius: 12px; box-shadow: var(--shadow); }
        .indicator-result-card.success { border-right-color: var(--success); }
        .indicator-result-card.danger { border-right-color: var(--danger); }
        .indicator-result-card header { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
        .indicator-title, .indicator-badges { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
        .indicator-title b { display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px;
            color: #fff; background: var(--secondary-navy); border-radius: 8px; font-size: 14px; }
        .indicator-result-card header h3 { margin: 0; }
        .indicator-result-card header span { padding: 3px 9px; border-radius: 999px; background: var(--secondary-bg);
            color: var(--muted); font-size: 12px; }
        .indicator-result-card.success .status-badge { color: var(--success); background: var(--success-bg); }
        .indicator-result-card.danger .status-badge { color: var(--danger); background: var(--danger-bg); }
        .impact-section { margin-top: 10px; padding-top: 9px; border-top: 1px solid #EEF1F5; }
        .impact-section h4 { margin: 0 0 6px; color: var(--muted); font-size: 12px; font-weight: 600; }
        .impact-row { display: grid; gap: 7px; }
        .impact-row.four { grid-template-columns: repeat(4, minmax(0, 1fr)); }
        .impact-row.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .impact-row > div { min-width: 0; }
        .impact-row span { display: block; color: var(--muted); font-size: 10px; line-height: 1.5; }
        .impact-row strong { display: block; margin-top: 1px; font-size: 14px; }
        .rank-comparison { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 7px; }
        .rank-comparison > div { min-width: 0; padding: 8px; background: var(--secondary-bg); border-radius: 8px; }
        .rank-comparison span { display: block; color: var(--muted); font-size: 10px; }
        .rank-comparison strong { display: block; margin-top: 2px; font-size: 15px; white-space: nowrap; }
        .rank-result strong { white-space: normal; }
        .indicator-result-card.success .rank-result strong { color: var(--success); }
        .indicator-result-card.danger .rank-result strong { color: var(--danger); }
        .impact-section.weighted { padding: 9px; background: var(--secondary-bg); border-radius: 9px; }
        .overall-effect { padding: 5px 7px; background: #EAF2F8; border-radius: 8px; }
        .overall-effect strong { color: var(--accent); font-size: 17px; }
        @container (max-width: 760px) { .indicator-result-grid { grid-template-columns: minmax(0, 1fr); } }
        @container (max-width: 500px) { .impact-row.four, .impact-row.three, .rank-comparison { grid-template-columns: minmax(0, 1fr); } }
        .result-action-title { color: var(--primary); font-weight: 700; margin-bottom: 8px; }
        .saved-scenario-card { display: flex; align-items: flex-start; justify-content: space-between;
            gap: 12px; margin: -1rem -1rem 10px; padding: 12px 14px; color: #fff;
            background: var(--primary); border-radius: 11px 11px 0 0; }
        .saved-scenario-card h3 { margin: 0; font-size: 17px !important; overflow-wrap: anywhere; }
        .saved-scenario-card h3, .saved-scenario-card p { color: #fff !important; }
        .saved-scenario-card p { margin: 2px 0 0; font-size: 13px; }
        .saved-scenario-card > span { flex: 0 0 auto; padding: 4px 10px; color: var(--accent);
            background: #fff; border: 1px solid #D9E2EC; border-radius: 999px; font-size: 12px; }
        .scenario-builder-header { display: flex; direction: rtl; align-items: center; justify-content: flex-start;
            gap: 18px; margin: -6px 0 18px; text-align: right; font-family: var(--font) !important; }
        .scenario-builder-header-icon { flex: 0 0 70px; width: 70px; height: 70px; display: inline-flex; align-items: center; justify-content: center;
            color: var(--accent); background: var(--accent-soft); border-radius: 12px; }
        .scenario-builder-header-icon svg { width: 42px; height: 42px; fill: none; stroke: currentColor; stroke-width: 1.8;
            stroke-linecap: round; stroke-linejoin: round; }
        .scenario-builder-header h1 { margin: 0 !important; color: var(--primary); text-align: right;
            font-size: 31px !important; line-height: 1.45 !important; font-weight: 700 !important; }
        .scenario-builder-header p { margin: 3px 0 0; color: var(--text-secondary); text-align: right; font-size: 15px; line-height: 1.8; }
        .scenario-name-panel { direction: rtl; font-family: var(--font) !important; }
        .scenario-name-panel + div { display: none; }
        .scenario-name-panel [data-testid="stWidgetLabel"],
        .scenario-name-panel [data-testid="stWidgetLabel"] * { text-align: right !important; font-weight: 600 !important; }
        .scenario-name-panel input { direction: rtl !important; text-align: right !important; }
        .scenario-save-status { min-height: 34px; display: inline-flex; direction: rtl; align-items: center; justify-content: center;
            gap: 8px; margin-top: 22px; padding: 5px 11px; color: #9a5a00; background: #fff2d6;
            border: 1px solid #ffd38a; border-radius: 8px; font-size: 13px; font-weight: 700; white-space: normal; }
        .scenario-save-status b { width: 10px; height: 10px; border-radius: 999px; background: #f59f00; flex: 0 0 10px; }
        .indicator-card-anchor { display: none; }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.indicator-card-anchor),
        [data-testid="stLayoutWrapper"]:has(.indicator-card-anchor) {
            min-height: 184px; background: #fff; border: 1px solid var(--border) !important;
            border-radius: 12px !important; box-shadow: var(--shadow-soft); transition: border-color .15s ease, background .15s ease, box-shadow .15s ease;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.indicator-card-anchor):hover,
        [data-testid="stLayoutWrapper"]:has(.indicator-card-anchor):hover {
            border-color: #c7a7dd !important; box-shadow: 0 8px 20px rgba(20,35,63,.08);
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.indicator-card-anchor.selected),
        [data-testid="stLayoutWrapper"]:has(.indicator-card-anchor.selected) {
            border: 2px solid var(--accent) !important; background: #fbf8fd; box-shadow: 0 0 0 2px rgba(108,47,143,.08);
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.indicator-card-anchor) [data-testid="stVerticalBlock"],
        [data-testid="stLayoutWrapper"]:has(.indicator-card-anchor) [data-testid="stVerticalBlock"] {
            min-height: 150px; gap: 10px; padding: 0;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.indicator-card-anchor) [data-testid="stCheckbox"],
        [data-testid="stLayoutWrapper"]:has(.indicator-card-anchor) [data-testid="stCheckbox"] { align-self: stretch; }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.indicator-card-anchor) [data-testid="stCheckbox"] label,
        [data-testid="stLayoutWrapper"]:has(.indicator-card-anchor) [data-testid="stCheckbox"] label { align-items: flex-start; font-weight: 800 !important; color: var(--primary); }
        .indicator-picker-meta { display: grid; gap: 8px; margin-top: auto; }
        .indicator-picker-meta span { display: flex; align-items: center; justify-content: space-between; gap: 10px;
            padding: 8px 10px; color: var(--text-secondary); background: #f8fafc; border: 1px solid #edf0f5;
            border-radius: 8px; font-size: 12px; line-height: 1.7; }
        .indicator-picker-meta .weight { color: var(--accent); background: var(--accent-soft); border-color: #ddcaeb; }
        .indicator-picker-meta b { color: var(--primary); font-size: 13px; font-weight: 800; overflow-wrap: anywhere; }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.scenario-edit-card) {
            margin-bottom: 16px; background: #fff; border: 1px solid var(--neutral-200) !important;
            border-radius: 13px !important; box-shadow: 0 3px 12px rgba(23, 36, 59, 0.06); overflow: hidden; font-family: var(--font) !important;
        }
        .scenario-edit-card { display: block; margin: -1rem -1rem 0; padding: 0; background: #fff; font-family: var(--font) !important; }
        .scenario-edit-card > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
            padding: 17px 18px 14px; background: #fff; border-bottom: 1px solid var(--neutral-200); }
        .indicator-edit-title { min-width: 0; display: grid; grid-template-columns: 38px minmax(0,1fr); align-items: center; gap: 10px; }
        .indicator-edit-icon { width: 38px; height: 38px; display: inline-flex; align-items: center; justify-content: center;
            color: var(--accent); background: var(--en-purple-50); border: 1px solid #e1d5ea; border-radius: 10px; }
        .indicator-edit-icon svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
        .scenario-edit-card h3 { margin: 0 !important; color: var(--en-navy-900); font-size: 17px !important; line-height: 1.65 !important; font-weight: 800 !important; overflow-wrap: anywhere; }
        .indicator-base-value { flex: 0 1 48%; min-width: 0; text-align: left; }
        .indicator-base-value span { display: block; color: var(--neutral-600); font-size: 12px; line-height: 1.7; font-weight: 600; }
        .indicator-base-value strong { display: block; color: var(--en-navy-800); font-size: clamp(15px, 1.55vw, 19px); line-height: 1.55; font-weight: 800; overflow-wrap: anywhere; }
        .scenario-edit-controls { padding: 15px 17px 0; background: #fff; }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.scenario-edit-card) [data-testid="stSelectbox"] [data-baseweb="select"],
        [data-testid="stVerticalBlockBorderWrapper"]:has(.scenario-edit-card) [data-testid="stTextInput"] input {
            min-height: 44px; background: #fff !important; border: 1px solid var(--neutral-300) !important; border-radius: 10px !important;
            direction: rtl !important; text-align: right !important; font-family: var(--font) !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.scenario-edit-card) [data-testid="stSelectbox"] [data-baseweb="select"]:focus-within,
        [data-testid="stVerticalBlockBorderWrapper"]:has(.scenario-edit-card) [data-testid="stTextInput"] input:focus {
            border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(101,50,138,.12) !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.scenario-edit-card) [data-testid="stRadio"] > div {
            display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 6px; padding: 4px;
            min-height: 44px; background: var(--neutral-50); border: 1px solid var(--neutral-200); border-radius: 10px;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.scenario-edit-card) [data-testid="stRadio"] label {
            justify-content: center; margin: 0 !important; padding: 7px 8px; border-radius: 8px; font-weight: 700 !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.scenario-edit-card) [data-testid="stRadio"] label:has(input:checked) { background: var(--success-bg); color: var(--success); box-shadow: inset 0 0 0 1px #b9dfca; }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.scenario-edit-card):has(.direction-decrease-active) [data-testid="stRadio"] label:has(input:checked) { background: var(--danger-bg); color: var(--danger); box-shadow: inset 0 0 0 1px #efc3c9; }
        .direction-decrease-active, .direction-increase-active { display: none; }
        .value-comparison-card { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; margin: 14px 17px 0; padding: 0; font-family: var(--font) !important; }
        .value-comparison-item { min-width: 0; min-height: 78px; display: grid; align-content: center; gap: 3px; padding: 11px 12px; background: var(--neutral-50); border: 1px solid var(--neutral-200); border-radius: 10px; }
        .value-comparison-item span { color: var(--neutral-700); font-size: 12px; line-height: 1.7; font-weight: 600; }
        .value-comparison-item b { font-size: 14px; line-height: 1; }
        .value-comparison-item strong { color: var(--en-navy-900); font-size: clamp(15px, 1.5vw, 18px); line-height: 1.55; font-weight: 800; overflow-wrap: anywhere; unicode-bidi: isolate; }
        .value-comparison-item.current { background: var(--en-navy-50); border-color: var(--en-navy-100); }
        .value-comparison-item.scenario { background: var(--en-purple-50); border-color: #e1d5ea; }
        .value-comparison-item.scenario strong { color: var(--accent); }
        .value-comparison-item.success { background: var(--success-bg); border-color: #cbe8d8; }
        .value-comparison-item.danger { background: var(--danger-bg); border-color: #f0c8ce; }
        .value-comparison-item.success strong, .value-comparison-item.success span, .value-comparison-item.success b { color: var(--success); }
        .value-comparison-item.danger strong, .value-comparison-item.danger span, .value-comparison-item.danger b { color: var(--danger); }
        .change-result-strip { display: inline-flex; align-items: center; gap: 7px; margin: 10px 17px 16px; padding: 7px 10px; border-radius: 10px; font-size: 13px; font-weight: 800; }
        .change-result-strip.success { color: var(--success); background: var(--success-bg); }
        .change-result-strip.danger { color: var(--danger); background: var(--danger-bg); }
        .change-result-strip.neutral { color: var(--neutral-700); background: var(--neutral-100); }
        [data-baseweb="popover"], [role="listbox"], [data-baseweb="menu"] { direction: rtl !important; text-align: right !important; font-family: var(--font) !important; }
        .scenario-review-summary { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 0;
            margin: 0 0 16px; padding: 8px; background: var(--surface); border: 1px solid var(--border);
            border-radius: 13px; box-shadow: var(--shadow-soft); font-family: var(--font) !important; }
        .scenario-review-summary > div { min-width: 0; display: grid; grid-template-columns: 38px minmax(0,1fr);
            align-items: center; gap: 10px; padding: 12px 14px; background: #fff; border-left: 1px solid #edf0f5; }
        .scenario-review-summary > div:last-child { border-left: 0; }
        .scenario-review-summary .branch { background: #f8fbff; }
        .scenario-review-summary .changes { background: #fbf8fd; }
        .scenario-review-summary .scenario { background: #f8fafc; }
        .review-summary-icon { width: 38px; height: 38px; display: inline-flex; align-items: center; justify-content: center;
            color: var(--accent); background: var(--accent-soft); border-radius: 10px; }
        .review-summary-icon svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
        .scenario-review-summary small, .scenario-review-summary em { display: block; color: var(--text-secondary); font-size: 12px; line-height: 1.7; font-style: normal; }
        .scenario-review-summary strong { display: block; color: var(--primary); font-size: 18px; font-weight: 800; overflow-wrap: anywhere; }
        .review-card-grid { container-type: inline-size; display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; margin-bottom: 12px; }
        .review-change-card { min-width: 0; padding: 18px; background: #fff; border: 1px solid var(--border);
            border-right: 4px solid #98a2b3; border-radius: 12px; box-shadow: var(--shadow-soft); font-family: var(--font) !important; }
        .review-change-card.success { border-right-color: var(--success); }
        .review-change-card.danger { border-right-color: var(--danger); }
        .review-change-card > header { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 14px;
            padding-bottom: 12px; border-bottom: 1px solid #edf0f5; }
        .review-change-card h3 { margin: 0 !important; font-size: 17px !important; font-weight: 800 !important; overflow-wrap: anywhere; }
        .change-mode-badge { flex: 0 0 auto; padding: 5px 10px; color: var(--accent); background: var(--accent-soft);
            border: 1px solid #ddcaeb; border-radius: 999px; font-size: 12px; font-weight: 700; }
        .review-flow { display: grid; grid-template-columns: minmax(0,1fr) 28px minmax(0,1fr); align-items: center; gap: 8px; }
        .review-flow div { min-width: 0; min-height: 86px; padding: 12px; background: #f8fafc; border-radius: 10px; }
        .review-flow div:last-child { background: #fbf8fd; border: 1px solid #ddcaeb; }
        .review-flow span, .review-meta span { display: block; color: var(--text-secondary); font-size: 12px; line-height: 1.7; }
        .review-flow strong { display: block; color: var(--primary); font-size: 17px; font-weight: 800; overflow-wrap: anywhere; }
        .review-flow b { color: var(--accent); text-align: center; font-size: 18px; }
        .review-result-strip { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 12px;
            padding: 9px 11px; background: var(--secondary-bg); border-radius: 10px; font-size: 13px; font-weight: 700; }
        .review-result-strip span { display: inline-flex; align-items: center; gap: 6px; }
        .review-change-card.success .review-result-strip { color: var(--success); background: var(--success-bg); }
        .review-change-card.danger .review-result-strip { color: var(--danger); background: var(--danger-bg); }
        @container (max-width: 720px) { .review-card-grid { grid-template-columns: minmax(0,1fr); } }
        @media (max-width: 760px) { .scenario-review-summary { grid-template-columns: minmax(0,1fr); } }
        .wizard-steps { box-sizing: border-box; width: 100%; display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(22px, .55fr) minmax(0, 1fr) minmax(22px, .55fr) minmax(0, 1fr) minmax(22px, .55fr) minmax(0, 1fr);
            gap: 0; align-items: start;
            margin: 18px 0 22px; padding: 22px 28px 18px; direction: rtl; background: var(--surface);
            border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow-soft); }
        .wizard-step { min-width: 0; display: grid; justify-items: center; align-content: start; gap: 9px;
            position: relative; color: #667085; text-align: center; font-family: var(--font) !important; }
        .wizard-connector { display: block; width: 100%; min-width: 0; height: 2px; margin-top: 21px;
            background: #d7dce5; align-self: start; justify-self: stretch; }
        .wizard-step-completed + .wizard-connector { background: #c7b4d8; }
        .wizard-step-index { width: 44px; height: 44px; display: inline-flex; align-items: center; justify-content: center;
            color: #344054; background: #fff; border: 1px solid #d7dce5; border-radius: 999px; box-shadow: 0 2px 6px rgba(20,35,63,.05);
            position: relative; z-index: 1; font-size: 17px; line-height: 1; font-weight: 800; text-align: center; }
        .wizard-step-label { display: block; max-width: 100%; color: inherit; font-size: 14px; line-height: 1.75;
            font-weight: 600; overflow-wrap: anywhere; text-align: center; }
        .wizard-step.active { color: var(--accent); font-weight: 700; }
        .wizard-step.active .wizard-step-index { color: #fff; background: var(--brand-purple);
            border-color: var(--brand-purple); box-shadow: 0 8px 18px rgba(108,47,143,.22); }
        .wizard-step-completed { color: var(--primary); }
        .wizard-step-completed .wizard-step-index { color: var(--accent); background: var(--accent-soft); border-color: #d8c5e6; }
        .wizard-step-future { color: #667085; }
        @media (max-width: 760px) {
            .wizard-steps { grid-template-columns: minmax(0, 1fr) minmax(14px, .35fr) minmax(0, 1fr) minmax(14px, .35fr) minmax(0, 1fr) minmax(14px, .35fr) minmax(0, 1fr);
                padding: 16px 10px; }
            .wizard-step-index { width: 38px; height: 38px; font-size: 15px; }
            .wizard-connector { margin-top: 18px; }
        }
        .branch-step-panel { margin: 0 0 10px; padding: 0; background: transparent;
            border: 0; border-radius: 0; box-shadow: none; font-family: var(--font) !important; }
        .branch-step-panel header { display: flex; flex-direction: column; gap: 4px; text-align: right; }
        .branch-step-panel h2 { margin: 0 !important; color: var(--primary); font-size: 21px !important; line-height: 1.65 !important;
            font-weight: 800 !important; }
        .branch-step-panel p { margin: 0; color: var(--text-secondary); font-size: 14px; line-height: 1.85; }
        .branch-info-alert { min-height: 48px; display: flex; direction: rtl; align-items: center; gap: 12px;
            margin: 10px 0 0; padding: 8px 13px; color: #1d4f91; background: #eff7ff;
            border: 1px solid #9bc8ff; border-radius: 8px; font-family: var(--font) !important; }
        .branch-info-alert span { flex: 0 0 30px; width: 30px; height: 30px; display: inline-flex; align-items: center; justify-content: center;
            color: #fff; background: #2f80ed; border-radius: 999px; font-size: 18px; font-weight: 800; text-align: center; }
        .branch-info-alert p { margin: 0; color: #1d4f91; font-size: 14px; line-height: 1.75; }
        .change-step-header { margin: 2px 0 12px; direction: rtl; font-family: var(--font) !important; }
        .change-step-header h2 { margin: 0 !important; color: var(--en-navy-900); font-size: 26px !important;
            line-height: 1.55 !important; font-weight: 800 !important; }
        .change-step-header p { margin: 2px 0 0; color: var(--neutral-700); font-size: 14px; line-height: 1.8; }
        .selected-branch-banner { min-height: 70px; display: flex; direction: rtl; align-items: center;
            justify-content: space-between; gap: 12px; margin: 0 0 16px; padding: 14px 16px; color: var(--en-navy-900);
            background: var(--en-purple-50); border: 1px solid #e1d5ea; border-radius: 12px; font-family: var(--font) !important;
            text-align: right; box-shadow: 0 3px 12px rgba(23, 36, 59, 0.04); }
        .selected-branch-icon { flex: 0 0 40px; width: 40px; height: 40px; display: inline-flex; align-items: center; justify-content: center;
            color: var(--accent); background: #fff; border: 1px solid #e1d5ea; border-radius: 11px; }
        .selected-branch-icon svg { width: 24px; height: 24px; fill: none; stroke: currentColor; stroke-width: 1.8;
            stroke-linecap: round; stroke-linejoin: round; }
        .selected-branch-text { min-width: 0; flex: 1 1 auto; display: grid; gap: 1px; }
        .selected-branch-text small { color: var(--neutral-600); font-size: 12px; line-height: 1.7; font-weight: 600; }
        .selected-branch-text strong { color: var(--en-navy-900); font-size: 16px; line-height: 1.7; font-weight: 800; overflow-wrap: anywhere; }
        .selected-branch-code { flex: 0 0 auto; display: inline-flex; align-items: center; gap: 5px; padding: 6px 10px;
            color: var(--accent); background: #fff; border: 1px solid #ddcaeb; border-radius: 999px; font-size: 12px; font-weight: 700; }
        .selected-branch-banner bdi { direction: rtl; unicode-bidi: isolate; font-weight: 800; }
        .branch-summary-panel { margin: 14px 0 4px; padding: 16px; background: var(--surface);
            border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow-soft);
            font-family: var(--font) !important; }
        .branch-summary-panel header { min-width: 0; margin-bottom: 14px; text-align: right; direction: rtl; }
        .branch-summary-panel h3 { margin: 0 !important; color: var(--primary); font-size: 18px !important; font-weight: 800 !important;
            overflow-wrap: anywhere; }
        .branch-summary-panel p { margin: 3px 0 0; color: var(--text-secondary); font-size: 13px; line-height: 1.8; }
        .branch-summary-panel bdi { direction: rtl; unicode-bidi: isolate; font-weight: 700; }
        .branch-info-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
        .branch-info-card { min-height: 102px; display: grid; direction: rtl; flex-direction: row; grid-template-columns: 54px minmax(0,1fr); align-items: center;
            gap: 14px; padding: 16px 18px; background: #fff; border: 1px solid #e4e8ef;
            border-radius: 12px; text-align: right; box-shadow: var(--shadow-soft); }
        .branch-info-content { min-width: 0; display: grid; gap: 4px; justify-items: start;
            align-content: center; text-align: right; overflow-wrap: anywhere; }
        .branch-info-content span { color: var(--text-secondary); font-size: 13px; line-height: 1.6; font-weight: 600; }
        .branch-info-content strong { color: var(--primary); font-size: 24px; line-height: 1.45; font-weight: 800; }
        .branch-info-icon { grid-column: 1; grid-row: 1; flex: 0 0 54px; width: 54px; height: 54px; display: inline-flex; align-items: center; justify-content: center;
            color: var(--accent); background: var(--accent-soft); border-radius: 999px; border: 1px solid #e1d5ea; flex-shrink: 0; }
        .branch-info-icon svg { width: 30px; height: 30px; fill: none; stroke: currentColor; stroke-width: 1.75;
            stroke-linecap: round; stroke-linejoin: round; }
        @media (max-width: 900px) { .branch-info-grid { grid-template-columns: minmax(0, 1fr); } }
        @media (max-width: 980px) {
            [data-testid="stHorizontalBlock"]:has(.scenario-edit-card) { flex-direction: column !important; }
            [data-testid="stHorizontalBlock"]:has(.scenario-edit-card) > [data-testid="column"] { width: 100% !important; flex: 1 1 auto !important; }
            [data-testid="stHorizontalBlock"]:has(.scenario-edit-card) > [data-testid="stColumn"] { width: 100% !important; flex: 1 1 100% !important; }
            [data-testid="column"]:has(.scenario-edit-card) { width: 100% !important; flex: 1 1 100% !important; min-width: 0 !important; }
            [data-testid="stColumn"]:has(.scenario-edit-card) { width: 100% !important; flex: 1 1 100% !important; min-width: 0 !important; }
        }
        @media (max-width: 640px) {
            .selected-branch-banner { align-items: flex-start; flex-wrap: wrap; }
            .selected-branch-code { margin-right: 52px; }
            .scenario-edit-card > header { flex-direction: column; }
            .indicator-base-value { text-align: right; }
            .value-comparison-card { grid-template-columns: minmax(0,1fr); }
        }
        .builder-action-row { margin-top: 18px; }
        .builder-action-row + [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-primary"] {
            background: var(--brand-purple) !important; border-color: var(--brand-purple) !important;
        }
        .builder-action-row + [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-secondary"] {
            min-height: 44px; border-radius: 8px;
        }
        .builder-action-row + [data-testid="stHorizontalBlock"] [data-testid="column"] {
            min-width: 132px !important; flex: 0 0 132px !important;
        }
        [data-testid="stVerticalBlock"]:has(.builder-action-row) [data-testid="stHorizontalBlock"]:has(button[data-testid="stBaseButton-primary"]) [data-testid="column"] {
            min-width: 132px !important; flex: 0 0 132px !important;
        }
        .builder-action-row + [data-testid="stHorizontalBlock"] button {
            display: inline-flex; align-items: center; justify-content: center; text-align: center !important;
            width: 100% !important; min-height: 44px; font-weight: 600 !important; line-height: 1.5 !important;
        }
        .process-line { padding:14px; border:1px solid #eaecf0; border-radius:12px;
            background:#fff; text-align:center; color:#344054; word-spacing:8px; }
        .calculation-detail-grid { display: grid; grid-template-columns: minmax(0,1fr); gap: 14px; margin: 8px 0 14px;
            font-family: var(--font) !important; }
        .calculation-detail-card { padding: 18px; background: #fff; border: 1px solid var(--border);
            border-right: 4px solid #98a2b3; border-radius: 12px; box-shadow: var(--shadow-soft); }
        .calculation-detail-card.success { border-right-color: var(--success); }
        .calculation-detail-card.danger { border-right-color: var(--danger); }
        .calculation-detail-card > header { display: flex; align-items: flex-start; justify-content: space-between;
            gap: 12px; padding-bottom: 12px; border-bottom: 1px solid #edf0f5; }
        .calculation-detail-card h3 { margin: 0 !important; color: var(--primary); font-size: 17px !important; font-weight: 800 !important; }
        .calculation-detail-card header span { display: block; color: var(--text-secondary); font-size: 12px; }
        .calculation-detail-card header b { padding: 5px 10px; color: var(--accent); background: var(--accent-soft);
            border-radius: 999px; font-size: 12px; white-space: nowrap; }
        .calculation-detail-card section { margin-top: 12px; }
        .calculation-detail-card h4 { margin: 0 0 7px; color: var(--primary); font-size: 13px; font-weight: 800; }
        .detail-pair, .detail-triplet { display: grid; gap: 8px; }
        .detail-pair { grid-template-columns: repeat(2,minmax(0,1fr)); }
        .detail-triplet { grid-template-columns: repeat(3,minmax(0,1fr)); }
        .detail-pair div, .detail-triplet div { min-width: 0; padding: 9px 10px; background: #f8fafc; border-radius: 9px; }
        .detail-pair span, .detail-triplet span { display: block; color: var(--text-secondary); font-size: 11px; line-height: 1.7; }
        .detail-pair strong, .detail-triplet strong { display: block; color: var(--primary); font-size: 14px; font-weight: 800; overflow-wrap: anywhere; }
        .calculation-detail-card details { margin-top: 12px; padding: 8px 10px; background: #fbfcfe; border: 1px solid #edf0f5; border-radius: 9px; }
        .calculation-detail-card summary { cursor: pointer; color: var(--accent); font-weight: 700; }
        .calculation-detail-card p { margin: 6px 0 0; color: var(--text-secondary); font-size: 12px; }
        .branch-result-section { margin: 16px 0; font-family: var(--font) !important; }
        .branch-result-section h3 { margin: 0 0 10px !important; color: var(--primary); font-size: 18px !important; font-weight: 800 !important; }
        .branch-result-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 14px; }
        .branch-result-card { min-width: 0; background: #fff; border: 1px solid var(--border);
            border-radius: 12px; box-shadow: var(--shadow-soft); overflow: hidden; }
        .branch-result-card > header { display: flex; align-items: center; justify-content: space-between; gap: 10px;
            padding: 13px 15px; background: #fbfcfe; border-bottom: 1px solid #edf0f5; }
        .branch-result-card header strong { display: inline-flex; align-items: center; gap: 8px; color: var(--primary); font-weight: 800; }
        .branch-result-card header svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.8; }
        .branch-result-card header span { color: var(--text-secondary); font-size: 12px; font-weight: 700; }
        .branch-result-row { display: grid; grid-template-columns: 38px minmax(0,1fr); gap: 10px;
            padding: 13px 15px; border-bottom: 1px solid #f0f2f6; }
        .branch-result-row:last-child { border-bottom: 0; }
        .branch-result-icon { width: 38px; height: 38px; display: inline-flex; align-items: center; justify-content: center;
            color: var(--accent); background: var(--accent-soft); border-radius: 10px; }
        .branch-result-icon svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.8; }
        .branch-result-row h4 { margin: 0 0 5px; color: var(--primary); font-size: 13px; font-weight: 800; }
        .branch-result-row div { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
        .branch-result-row b { color: var(--primary); font-size: 13px; }
        .branch-result-row i { color: var(--accent); font-style: normal; }
        .branch-result-row em { display: inline-flex; margin-top: 6px; padding: 4px 8px; border-radius: 999px;
            background: var(--secondary-bg); color: var(--text-secondary); font-style: normal; font-size: 12px; font-weight: 700; }
        .branch-result-row.success em { color: var(--success); background: var(--success-bg); }
        .branch-result-row.danger em { color: var(--danger); background: var(--danger-bg); }
        .results-workspace-header { display: flex; direction: rtl; align-items: center; justify-content: space-between; gap: 14px; margin: 4px 0 12px; font-family: var(--font) !important; }
        .results-workspace-header h1 { margin: 0 !important; color: var(--en-navy-900); font-size: 27px !important; line-height: 1.55 !important; font-weight: 800 !important; }
        .results-workspace-header p { margin: 2px 0 0; color: var(--neutral-700); font-size: 14px; line-height: 1.8; }
        .results-workspace-header > span { flex: 0 0 auto; padding: 5px 10px; color: var(--accent); background: var(--en-purple-50); border: 1px solid #e1d5ea; border-radius: 999px; font-size: 12px; font-weight: 700; }
        .results-context-strip { display: grid; grid-template-columns: 38px minmax(0,1fr); align-items: center; gap: 10px; margin: 0 0 14px; padding: 12px 14px; background: var(--en-purple-50); border: 1px solid #e1d5ea; border-radius: 12px; box-shadow: 0 3px 12px rgba(23,36,59,.04); font-family: var(--font) !important; }
        .results-context-icon { width: 38px; height: 38px; display: inline-flex; align-items: center; justify-content: center; color: var(--accent); background: #fff; border: 1px solid #e1d5ea; border-radius: 10px; }
        .results-context-icon svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
        .results-context-strip > div { min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 7px; }
        .results-context-strip strong, .results-context-strip span:not(.results-context-icon) { display: inline-flex; align-items: center; min-height: 26px; padding: 3px 8px; background: #fff; border: 1px solid var(--neutral-200); border-radius: 999px; color: var(--en-navy-800); font-size: 12px; font-weight: 700; }
        .results-context-strip bdi { unicode-bidi: isolate; direction: rtl; }
        .result-glance { margin: 0 0 14px; font-family: var(--font) !important; }
        .result-glance > header h2 { margin: 0 0 9px !important; color: var(--en-navy-900); font-size: 19px !important; font-weight: 800 !important; }
        .result-glance > div { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 10px; }
        .result-glance-card { min-width: 0; min-height: 150px; display: grid; gap: 11px; padding: 16px; background: #fff; border: 1px solid var(--neutral-200); border-radius: 13px; box-shadow: 0 3px 12px rgba(23,36,59,.06); }
        .result-glance-card header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
        .result-glance-card h3 { margin: 0 !important; color: var(--en-navy-900); font-size: 15px !important; font-weight: 800 !important; }
        .result-trend-icon { flex: 0 0 26px; width: 26px; height: 26px; display: inline-flex; align-items: center; justify-content: center; border-radius: 999px; background: var(--neutral-100); color: var(--neutral-700); font-size: 15px; line-height: 1; font-weight: 900; overflow: hidden; }
        .result-trend-icon.small { flex-basis: 18px; width: 18px; height: 18px; font-size: 11px; }
        .result-glance-card.success .result-trend-icon { color: var(--success); background: var(--success-bg); }
        .result-glance-card.danger .result-trend-icon { color: var(--danger); background: var(--danger-bg); }
        .result-glance-values { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; }
        .result-glance-values div { min-width: 0; padding: 8px; background: var(--neutral-50); border-radius: 9px; }
        .result-glance-values span { display: block; color: var(--neutral-600); font-size: 11px; line-height: 1.7; font-weight: 700; }
        .result-glance-values strong { display: block; color: var(--en-navy-900); font-size: clamp(17px,1.55vw,23px); line-height: 1.5; font-weight: 800; overflow-wrap: anywhere; }
        .result-glance-values .scenario { color: var(--accent); }
        .result-change-pill { display: inline-flex; align-items: center; gap: 6px; margin: 0; padding: 6px 9px; border-radius: 999px; background: var(--neutral-100); color: var(--neutral-700); font-size: 12px; font-weight: 800; }
        .result-glance-card.success .result-change-pill { color: var(--success); background: var(--success-bg); }
        .result-glance-card.danger .result-change-pill { color: var(--danger); background: var(--danger-bg); }
        [data-testid="stTabs"] { font-family: var(--font) !important; }
        [data-testid="stTabs"] [role="tablist"] { position: sticky; top: calc(var(--streamlit-header-offset) + 4px); z-index: 5; display: flex; gap: 6px; overflow-x: auto; padding: 8px; background: rgba(255,255,255,.96); border: 1px solid var(--neutral-200); border-radius: 12px; box-shadow: 0 3px 12px rgba(23,36,59,.05); }
        [data-testid="stTabs"] [role="tab"] { min-height: 38px; padding: 6px 10px; border-radius: 9px; color: var(--neutral-700); font-size: 13px; font-weight: 800; white-space: nowrap; }
        [data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: var(--accent); background: var(--en-purple-50); }
        [data-testid="stTabs"] [role="tab"]:focus-visible { outline: 3px solid rgba(101,50,138,.18); outline-offset: 2px; }
        .results-tab-panel { margin: 14px 0 10px; font-family: var(--font) !important; }
        .results-tab-panel header h2 { margin: 0 !important; color: var(--en-navy-900); font-size: 19px !important; font-weight: 800 !important; }
        .results-tab-panel header p { margin: 2px 0 10px; color: var(--neutral-700); font-size: 13px; line-height: 1.8; }
        .calculation-table-wrap, .branch-impact-table-wrap { max-width: 100%; overflow-x: auto; border: 1px solid var(--neutral-200); border-radius: 12px; background: #fff; box-shadow: 0 3px 12px rgba(23,36,59,.04); }
        .calculation-table, .branch-impact-table { width: 100%; min-width: 1080px; border-collapse: separate; border-spacing: 0; direction: rtl; font-family: var(--font) !important; }
        .calculation-table th, .branch-impact-table th { position: sticky; top: 0; z-index: 1; padding: 9px 10px; color: var(--en-navy-800); background: var(--neutral-50); border-bottom: 1px solid var(--neutral-200); font-size: 11px; line-height: 1.6; font-weight: 800; text-align: right; white-space: nowrap; }
        .calculation-table td, .branch-impact-table td { padding: 9px 10px; border-bottom: 1px solid #eef1f5; color: var(--neutral-900); font-size: 12px; line-height: 1.65; vertical-align: middle; text-align: right; }
        .calculation-table tbody tr:hover, .branch-impact-table tbody tr:hover { background: var(--en-purple-50); }
        .calculation-table tr.changed { background: #fcf9fd; box-shadow: inset -4px 0 0 #d8c5e6; }
        .calculation-table tr.calc-summary-row td { background: var(--en-navy-50); color: var(--en-navy-900); font-weight: 900; border-top: 2px solid var(--en-navy-100); }
        .indicator-cell strong { display: block; max-width: 180px; color: var(--en-navy-900); font-weight: 900; overflow-wrap: anywhere; }
        .indicator-cell em { display: inline-flex; margin-top: 4px; padding: 2px 7px; color: var(--accent); background: var(--en-purple-50); border: 1px solid #e1d5ea; border-radius: 999px; font-size: 10px; font-style: normal; font-weight: 800; }
        .indicator-cell em.neutral { color: var(--neutral-600); background: var(--neutral-100); border-color: var(--neutral-200); }
        .calculation-table .scenario, .branch-impact-table .scenario { color: var(--accent); font-weight: 800; }
        .calculation-table .success, .branch-impact-table .success { color: var(--success); font-weight: 800; }
        .calculation-table .danger, .branch-impact-table .danger { color: var(--danger); font-weight: 800; }
        .result-calc-details { display: block; margin: 0; padding: 0; font-size: 12px; line-height: 1; border: 0; transform: none; }
        .result-calc-details > summary.calc-detail-toggle { width: 34px; max-width: 34px; height: 30px; max-height: 30px; display: block; cursor: pointer; color: var(--accent); background: var(--en-purple-50); border: 1px solid #e1d5ea; border-radius: 8px; font-size: 14px; line-height: 1; font-weight: 900; list-style: none; list-style-type: none; overflow: hidden; transform: none; }
        .result-calc-details > summary.calc-detail-toggle::-webkit-details-marker { display: none; }
        .result-calc-details > summary.calc-detail-toggle::marker { content: ""; display: none; font-size: 0; }
        .result-calc-details > summary.calc-detail-toggle .calc-detail-chevron { width: 18px; max-width: 18px; height: 18px; max-height: 18px; display: flex; align-items: center; justify-content: center; margin: 5px auto; padding: 0; border: 0; font-size: 14px; line-height: 1; overflow: hidden; transform: none; }
        .result-calc-details[open] > summary.calc-detail-toggle { background: var(--accent); color: #fff; }
        .calc-detail-panel { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 7px; width: min(740px, 70vw); margin-top: 8px; padding: 10px; background: var(--en-purple-50); border: 1px solid #e1d5ea; border-radius: 10px; }
        .calc-detail-panel span { min-width: 0; display: grid; gap: 2px; padding: 6px 8px; background: #fff; border-radius: 8px; }
        .calc-detail-panel small { color: var(--neutral-600); font-size: 11px; font-weight: 700; }
        .calc-detail-panel b { color: var(--en-navy-900); font-size: 12px; overflow-wrap: anywhere; unicode-bidi: isolate; }
        .results-chip-row, .branch-impact-summary { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 10px; }
        .results-chip-row span, .branch-impact-summary span { display: inline-flex; gap: 6px; align-items: center; padding: 7px 10px; background: #fff; border: 1px solid var(--neutral-200); border-radius: 999px; color: var(--neutral-700); font-size: 12px; font-weight: 800; }
        .changed-indicators-panel > div:last-child { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 10px; }
        .changed-indicator-card { padding: 13px; background: #fff; border: 1px solid var(--neutral-200); border-radius: 12px; box-shadow: 0 3px 12px rgba(23,36,59,.04); }
        .changed-indicator-card.success { border-right: 4px solid var(--success); }
        .changed-indicator-card.danger { border-right: 4px solid var(--danger); }
        .changed-indicator-card header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
        .changed-indicator-card h3 { margin: 0 !important; font-size: 15px !important; font-weight: 900 !important; }
        .changed-indicator-card header span { color: var(--accent); font-size: 12px; font-weight: 800; }
        .changed-indicator-card > div { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 7px; }
        .changed-indicator-card > div span { padding: 7px 8px; background: var(--neutral-50); border-radius: 8px; color: var(--neutral-700); font-size: 11px; font-weight: 700; }
        .changed-indicator-card b { display: block; margin-top: 2px; color: var(--en-navy-900); font-size: 12px; overflow-wrap: anywhere; }
        .branch-impact-table tr.focus td { background: var(--en-purple-50); box-shadow: inset -4px 0 0 var(--accent); }
        .rank-preview { margin-top: 12px; }
        .rank-preview h3 { margin: 0 0 8px !important; font-size: 16px !important; font-weight: 900 !important; }
        .results-empty-state { min-height: 96px; display: grid; place-items: center; gap: 8px; padding: 18px; background: var(--neutral-50); border: 1px solid var(--neutral-200); border-radius: 12px; color: var(--neutral-700); }
        .results-empty-state svg { width: 28px; height: 28px; fill: none; stroke: currentColor; stroke-width: 1.8; }
        .results-empty-state p { margin: 0; font-size: 13px; font-weight: 700; }
        .results-action-bar { margin-top: 16px; }
        .results-action-bar + [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-primary"] { background: var(--accent) !important; border-color: var(--accent) !important; }
        .results-action-bar + [data-testid="stHorizontalBlock"] button { min-height: 44px; border-radius: 10px !important; font-weight: 800 !important; }
        .results-action-bar + [data-testid="stHorizontalBlock"] [data-testid="column"],
        .results-action-bar + [data-testid="stHorizontalBlock"] [data-testid="stColumn"] { min-width: 150px !important; flex: 0 0 150px !important; }
        @media (max-width: 1100px) { .result-glance > div { grid-template-columns: repeat(2,minmax(0,1fr)); } }
        @media (max-width: 760px) {
            [data-testid="stSidebar"][aria-expanded="false"] { width: 0 !important; min-width: 0 !important; transform: translateX(100%) !important; pointer-events: none !important; }
            [data-testid="stSidebar"][aria-expanded="false"] * { pointer-events: none !important; }
            .scenario-review-summary, .branch-result-grid, .detail-pair, .detail-triplet { grid-template-columns: minmax(0,1fr); }
            .scenario-review-summary > div { border-left: 0; border-bottom: 1px solid #edf0f5; }
            .scenario-review-summary > div:last-child { border-bottom: 0; }
            .results-workspace-header { align-items: flex-start; flex-direction: column; }
            .result-glance > div, .changed-indicators-panel > div:last-child { grid-template-columns: minmax(0,1fr); }
            .calc-detail-panel { grid-template-columns: repeat(2,minmax(0,1fr)); width: min(600px, 80vw); }
            .results-action-bar + [data-testid="stHorizontalBlock"] [data-testid="column"],
            .results-action-bar + [data-testid="stHorizontalBlock"] [data-testid="stColumn"] { min-width: 120px !important; flex: 0 0 120px !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    render_navigation(active_view=active_view, active_scenario=active_scenario)
