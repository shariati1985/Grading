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
            --primary-navy: #14233f;
            --brand-purple: #6c2f8f;
            --brand-purple-dark: #51206f;
            --brand-purple-light: #f1e9f7;
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
            --font: "Segoe UI", Tahoma, Arial, sans-serif;
            --nav-width: 292px;
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
            padding: 1.4rem 2rem 3rem;
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
        [data-testid="stSidebarUserContent"] { padding: 22px 14px; }
        @media (min-width: 801px) {
            [data-testid="stSidebarCollapseButton"] { display: none !important; }
        }
        .scenario-nav { display: grid; gap: 9px; }
        .utility-nav { display: grid; gap: 9px; padding-bottom: 14px; margin-bottom: 14px; }
        .scenario-nav-link {
            display: flex;
            align-items: center;
            flex-direction: row-reverse;
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
            flex: 0 0 25px;
            width: 25px;
            height: 25px;
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
            .home-page-header h1 { font-size: 24px !important; overflow-wrap: anywhere; }
            .home-page-header p { font-size: 14px; }
            .home-decision-panel { min-height: 260px; padding: 28px 18px; }
            .home-decision-panel h2 { font-size: 22px !important; }
            .home-decision-panel p { font-size: 14px; }
            .scenario-card-grid,
            .home-overview-grid { grid-template-columns: minmax(0, 1fr) !important; gap: 14px; }
            .scenario-card { min-height: 206px; }
        }
        .home-page-header { position: relative; padding: 4px 0 18px; text-align: center; }
        .home-page-header h1 { margin: 10px 0 2px !important; text-align: center; font-size: 31px !important; font-weight: 800 !important; color: var(--primary); }
        .home-page-header p { margin: 0 auto; text-align: center; color: var(--text-secondary); font-size: 16px; max-width: 760px; }
        .home-user-chip { display: inline-flex; align-items: center; gap: 10px; direction: rtl; color: var(--primary); }
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
        .decision-panel-action { position: relative; z-index: 1; min-height: 46px; display: inline-flex; align-items: center; gap: 12px;
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
        .scenario-card-start { align-self: stretch; min-height: 44px; display: inline-flex; justify-content: center; align-items: center; gap: 12px;
            padding-inline: 12px; color: var(--accent); background: transparent; border-top: 1px solid var(--border); font-weight: 700; font-size: 13px; }
        .scenario-card-start b { font-size: 20px; line-height: 1; }
        .home-overview-grid { container-type: inline-size; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 22px; margin: 0 0 26px; }
        .home-overview-grid article { min-height: 104px; display: flex; flex-direction: row-reverse; align-items: center; justify-content: space-between; gap: 16px;
            padding: 18px 22px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow-soft); }
        .home-overview-grid b { display: block; color: var(--primary); font-size: 25px; line-height: 1.5; font-weight: 800; text-align: right; }
        .home-overview-grid small { display: block; color: var(--text-secondary); font-size: 13px; line-height: 1.7; }
        .overview-icon { flex: 0 0 54px; width: 54px; height: 54px; border-radius: 999px; background: var(--accent-soft); border: 1px solid #e1d5ea; position: relative; }
        .overview-icon::before { content: ""; position: absolute; inset: 14px; border: 2px solid var(--accent); border-radius: 3px; }
        .overview-icon.bank::before { inset: 16px 12px 14px; border-width: 0 0 2px; box-shadow: inset 0 2px 0 var(--accent); transform: perspective(20px) rotateX(18deg); }
        .overview-icon.clock::before { border-radius: 999px; }
        .overview-icon.clock::after { content: ""; position: absolute; width: 2px; height: 15px; right: 26px; top: 17px; background: var(--accent); box-shadow: -7px 9px 0 -1px var(--accent); transform-origin: bottom; }
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
