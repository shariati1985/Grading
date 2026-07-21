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
            --app-bg: #FFFFFF;
            --surface: #FFFFFF;
            --secondary-bg: #F5F7FA;
            --primary: #102A43;
            --secondary-navy: #173F5F;
            --accent: #24527A;
            --success: #16835B;
            --success-bg: #E9F7F1;
            --danger: #C43D4B;
            --danger-bg: #FDEDEF;
            --warning: #B7791F;
            --warning-bg: #FFF6E5;
            --muted: #627D98;
            --border: #D9E2EC;
            --radius: 12px;
            --shadow: 0 4px 14px rgba(16, 42, 67, 0.07);
            --font: "Segoe UI", Tahoma, Arial, sans-serif;
            --nav-width: 250px;
        }

        html, body, button, input, textarea, select,
        [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] {
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
        .bank-hero { display: flex; align-items: center; gap: 18px; padding: 22px 24px; margin-bottom: 18px;
            color: #fff; background: linear-gradient(135deg, var(--primary), var(--secondary-navy));
            border-radius: var(--radius); box-shadow: var(--shadow); }
        .bank-hero h1 { margin: 0 !important; color: #fff !important; }
        .bank-hero p { margin: 3px 0 0; color: #D9E2EC; }
        .bank-logo-slot, .nav-brand-mark:empty { display: none; }
        .bank-logo-slot:has(img), .nav-brand-mark:has(img) { display: inline-flex; }
        .bank-logo-slot { flex: 0 0 68px; width: 68px; height: 54px; align-items: center; justify-content: center;
            padding: 6px; background: #fff; border-radius: 9px; }
        .bank-logo-slot img { max-width: 100%; max-height: 100%; object-fit: contain; }

        /* Keep Streamlit's native sidebar layout so its reserved space remains
           correct under browser zoom and viewport resizing. */
        [data-testid="stSidebar"] {
            width: var(--nav-width) !important;
            min-width: var(--nav-width) !important;
            background: var(--surface);
            border-right: 1px solid var(--border);
            box-shadow: 4px 0 18px rgba(16, 24, 40, .035);
        }
        [data-testid="stSidebar"] > div { width: var(--nav-width) !important; }
        [data-testid="stSidebar"] * { direction: rtl; text-align: right; }
        [data-testid="stSidebarNav"] { display: none !important; }
        [data-testid="stSidebarUserContent"] { padding: 18px 12px; }
        .scenario-nav { display: grid; gap: 5px; }
        .utility-nav { display: grid; gap: 5px; padding-bottom: 10px; margin-bottom: 10px;
            border-bottom: 1px solid var(--border); }
        .scenario-nav-link {
            display: flex;
            align-items: center;
            gap: 10px;
            min-height: 46px;
            margin: 3px 0;
            padding: 0 14px;
            border-radius: 10px;
            color: #344054;
            text-decoration: none;
            font-size: 15px;
            white-space: normal;
            overflow-wrap: anywhere;
        }
        .scenario-nav-link:hover {
            background: #EAF2F8;
            color: var(--accent);
        }
        .scenario-nav-link.active {
            color: var(--accent);
            background: #EAF2F8;
            font-weight: 600;
            box-shadow: inset -3px 0 0 var(--accent);
        }
        .nav-brand { display: flex; direction: rtl; align-items: center; gap: 10px;
            padding: 8px 8px 18px; margin-bottom: 8px; border-bottom: 1px solid var(--border); }
        .nav-brand-mark { direction: ltr; display: inline-flex; align-items: center; justify-content: center;
            width: 40px; height: 40px; border-radius: 11px; color: #fff; background: var(--primary);
            font-weight: 600; font-size: 14px; flex: 0 0 40px; overflow: hidden; }
        .nav-brand-mark img { width: 100%; height: 100%; object-fit: contain; }
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
            color: #fff !important; background: var(--secondary-navy) !important;
            border-color: var(--accent) !important; border-radius: 10px; font-weight: 600;
        }
        [data-testid="stBaseButton-primary"]:hover { background: var(--accent) !important; border-color: var(--accent) !important; }
        [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button {
            min-height: 42px; width: auto !important; max-width: 100%; border-radius: 10px;
            white-space: normal; overflow-wrap: anywhere;
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
            [data-testid="stMainBlockContainer"] { padding: 1rem .7rem 2rem; }
            h1 { font-size: 25px !important; }
            h2 { font-size: 20px !important; }
            [data-testid="column"] { min-width: 100% !important; }
        }
        .scenario-card-grid { container-type: inline-size; display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 24px; }
        .scenario-card { min-width: 0; min-height: 240px; display: flex; flex-direction: column;
            padding: 20px; text-align: right; color: var(--primary); text-decoration: none;
            background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
            box-shadow: var(--shadow); transition: transform .15s ease, border-color .15s ease, box-shadow .15s ease; }
        .scenario-card:hover, .scenario-card:focus-visible { color: var(--primary); border-color: #BDB4FF;
            box-shadow: 0 8px 24px rgba(16,24,40,.10); transform: translateY(-2px); outline: none; }
        .scenario-card-icon { font-size: 30px; line-height: 1; font-weight: 800; }
        .scenario-card.purple .scenario-card-icon { color: #6941c6; }
        .scenario-card.orange .scenario-card-icon { color: #dc6803; }
        .scenario-card.green .scenario-card-icon { color: #039855; }
        .scenario-card h3 { margin: 13px 0 6px; }
        .scenario-card p { color: #667085; line-height: 1.9; margin: 0 0 18px; flex: 1; }
        .scenario-card-start { align-self: stretch; min-height: 44px; display: inline-flex;
            justify-content: center; align-items: center; padding-inline: 24px; color: #fff;
            background: var(--accent); border-radius: 10px; font-weight: 600; }
        @container (max-width: 1080px) { .scenario-card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
        @container (max-width: 620px) { .scenario-card-grid { grid-template-columns: minmax(0, 1fr); } }
        .numeric-ltr { direction: ltr; unicode-bidi: isolate; text-align: right; font-variant-numeric: tabular-nums;
            max-width: 100%; overflow: hidden; word-break: keep-all; text-overflow: ellipsis; white-space: nowrap; }
        .value-comparison-card { container-type: inline-size; display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
        .value-comparison-item { min-width: 0; padding: 14px; border: 1px solid var(--border);
            border-radius: 11px; background: #F8FAFC; }
        .value-comparison-item span { display: block; color: var(--muted); font-size: 13px; }
        .value-comparison-item strong { display: block; margin-top: 5px; color: var(--primary);
            font-size: clamp(15px, 2.2cqi, 22px); line-height: 1.5; }
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
        .comparison-strip-item { min-width: 0; padding: 14px 16px; background: var(--surface); border: 0; }
        .comparison-strip-item.success p { color: var(--success); background: var(--success-bg); }
        .comparison-strip-item.danger p { color: var(--danger); background: var(--danger-bg); }
        .comparison-strip-item h3 { margin: 0 0 8px; font-size: 15px !important; }
        .comparison-values { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
        .comparison-values div { min-width: 0; padding: 7px 8px; background: #F8FAFC; border-radius: 8px; }
        .comparison-values span { display: block; color: var(--muted); font-size: 11px; }
        .comparison-values strong { display: block; font-size: 18px; }
        .comparison-strip-item p { margin: 8px 0 0; padding: 6px 8px; color: var(--muted); background: var(--secondary-bg); border-radius: 7px; font-size: 12px; font-weight: 600; }
        .comparison-strip-item p span { display: block; font-size: 10px; font-weight: 400; }
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
        .wizard-steps { display:flex; gap:8px; margin:10px 0 24px; direction:rtl; }
        .wizard-step { flex:1; padding:10px; border-radius:10px; background:#f2f4f7;
            color:#667085; text-align:center; border:1px solid #eaecf0; }
        .wizard-step.active { background:#eef4ff; color:#3538cd; border-color:#c7d7fe; font-weight:700; }
        .process-line { padding:14px; border:1px solid #eaecf0; border-radius:12px;
            background:#fff; text-align:center; color:#344054; word-spacing:8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    render_navigation()
