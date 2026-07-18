"""Application shell and centralized banking design system."""

from __future__ import annotations

import streamlit as st

from .navigation import render_navigation


def apply_global_styles() -> None:
    """Render custom navigation and apply the complete responsive visual shell."""
    st.markdown(
        """
        <style>
        :root {
            --app-bg: #F5F7FB;
            --surface: #FFFFFF;
            --primary: #172554;
            --accent: #6D4AFF;
            --success: #178A61;
            --danger: #C43F3A;
            --warning: #B7791F;
            --muted: #667085;
            --border: #E2E7F0;
            --radius: 14px;
            --shadow: 0 4px 18px rgba(16, 24, 40, 0.06);
            --font: "Segoe UI", Tahoma, Arial, sans-serif;
            --nav-width: 250px;
        }

        html, body, [class*="st-"], button, input, textarea, select {
            font-family: var(--font) !important;
            letter-spacing: normal !important;
        }
        html, body, [data-testid="stAppViewContainer"] {
            direction: rtl;
            text-align: right;
            color: var(--primary);
            background: var(--app-bg);
            font-size: 15px;
            line-height: 1.75;
            overflow-x: hidden;
        }
        [data-testid="stAppViewContainer"] > .main {
            margin-right: var(--nav-width) !important;
            margin-left: 0 !important;
            width: calc(100% - var(--nav-width));
        }
        [data-testid="stMainBlockContainer"] {
            width: min(100%, 1320px);
            max-width: 1320px;
            margin-inline: auto;
            padding: 1.35rem 1.75rem 3rem;
            overflow-x: clip;
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

        /* Fixed custom right navigation; the native auto-generated menu stays hidden. */
        [data-testid="stSidebar"] {
            position: fixed !important;
            right: 0 !important;
            left: auto !important;
            top: 0;
            width: var(--nav-width) !important;
            min-width: var(--nav-width) !important;
            height: 100vh;
            background: var(--surface);
            border-left: 1px solid var(--border);
            box-shadow: -4px 0 18px rgba(16, 24, 40, .035);
        }
        [data-testid="stSidebar"] > div { width: var(--nav-width) !important; }
        [data-testid="stSidebar"] * { direction: rtl; text-align: right; }
        [data-testid="stSidebarNav"] { display: none !important; }
        [data-testid="stSidebarUserContent"] { padding: 18px 12px; }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a {
            display: flex;
            align-items: center;
            min-height: 46px;
            margin: 3px 0;
            padding: 0 14px;
            border-radius: 10px;
            color: #344054;
            text-decoration: none;
            font-size: 15px;
            white-space: nowrap;
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {
            background: #F0EEFF;
            color: var(--accent);
        }
        [data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] {
            color: var(--accent);
            background: #EFECFF;
            font-weight: 600;
            box-shadow: inset -3px 0 0 var(--accent);
        }
        .nav-brand { display: flex; direction: rtl; align-items: center; gap: 10px;
            padding: 8px 8px 18px; margin-bottom: 8px; border-bottom: 1px solid var(--border); }
        .nav-brand-mark { direction: ltr; display: inline-flex; align-items: center; justify-content: center;
            width: 40px; height: 40px; border-radius: 11px; color: #fff; background: var(--primary);
            font-weight: 600; font-size: 14px; flex: 0 0 40px; }
        .nav-brand strong { display: block; font-size: 14px; font-weight: 600; color: var(--primary); }
        .nav-brand small { display: block; font-size: 12px; color: var(--muted); margin-top: 2px; }

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
            min-height: 44px; width: auto !important; padding-inline: 28px !important;
            color: #fff !important; background: var(--accent) !important;
            border-color: var(--accent) !important; border-radius: 10px; font-weight: 600;
        }
        [data-testid="stBaseButton-primary"]:hover { background: #5A38E6 !important; border-color: #5A38E6 !important; }
        [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button {
            min-height: 42px; width: auto !important; border-radius: 10px;
        }
        [data-testid="stTextInput"] input, [data-testid="stSelectbox"] > div,
        [data-testid="stMultiSelect"] > div { border-radius: 9px; }
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
            [data-testid="stMainBlockContainer"] { padding-inline: 1rem; }
            [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 12px; }
            [data-testid="column"] { min-width: min(100%, 300px) !important; flex: 1 1 300px !important; }
            .kpi-panel-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 800px) {
            [data-testid="stAppViewContainer"] > .main { margin-right: 0 !important; width: 100%; }
            [data-testid="stMainBlockContainer"] { padding: 1rem .7rem 2rem; }
            h1 { font-size: 25px !important; }
            h2 { font-size: 20px !important; }
            [data-testid="column"] { min-width: 100% !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    render_navigation()
