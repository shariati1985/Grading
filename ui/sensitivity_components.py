"""Small reusable renderers for the sensitivity workspace."""

from __future__ import annotations

import html

import streamlit as st

from ui.navigation import scenario_href
from ui.navigation import icon_svg
from ui.sensitivity_labels import SCENARIO_DEFINITIONS
from ui.formatters import format_compact_number, format_percentage, persian_digits


def render_scenario_cards() -> None:
    """Render three fully clickable scenario cards from the shared definitions."""
    cards = []
    for item in SCENARIO_DEFINITIONS:
        href = scenario_href(item.scenario_type)
        cards.append(
            f'<a class="scenario-card {html.escape(item.color)}" href="{href}" target="_self">'
            f'<span class="scenario-card-icon">{icon_svg(item.icon)}</span>'
            f'<h3>{html.escape(item.label)}</h3><p>{html.escape(item.description)}</p>'
            f'<span class="scenario-card-start">ایجاد {html.escape(item.label)} <b aria-hidden="true">←</b></span></a>'
        )
    st.markdown(f'<div class="scenario-card-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def value_comparison_html(current: float, scenario: float) -> str:
    """Responsive, non-truncating raw-value comparison for one indicator."""
    difference = float(scenario) - float(current)
    percent = None if float(current) == 0 else difference / float(current) * 100.0
    values = (
        ("مقدار فعلی", format_compact_number(current)),
        ("مقدار جدید سناریو", format_compact_number(scenario)),
        ("تفاوت مطلق", format_compact_number(difference)),
        ("تفاوت درصدی", "تعریف‌نشده برای مبنای صفر" if percent is None else format_percentage(percent)),
    )
    cells = "".join(
        f'<div class="value-comparison-item"><span>{html.escape(label)}</span>'
        f'<strong class="numeric-ltr">{html.escape(value)}</strong></div>'
        for label, value in values
    )
    return f'<div class="value-comparison-card">{cells}</div>'


def render_value_comparison(current: float, scenario: float) -> None:
    st.markdown(value_comparison_html(current, scenario), unsafe_allow_html=True)


def summary_cards_html(items: list[dict[str, str]], changed_count: int = 0) -> str:
    cards = "".join(
        f'<section class="comparison-strip-item {html.escape(item.get("tone", "neutral"))}">'
        f'<h3>{html.escape(item["label"])}</h3><div class="comparison-values">'
        f'<div><span>وضعیت فعلی</span><strong class="numeric-ltr" dir="ltr">{html.escape(item["current"])}</strong></div>'
        f'<div><span>وضعیت سناریو</span><strong class="numeric-ltr" dir="ltr">{html.escape(item["scenario"])}</strong></div></div>'
        f'<p><span>نتیجه تغییر</span>{html.escape(item["change"])}</p></section>'
        for item in items
    )
    return (
        '<div class="comparison-strip-header"><div><strong>جمع‌بندی مدیریتی سناریو</strong>'
        '<small>مقایسه وضعیت فعلی با نتیجه اجرای مدل رسمی</small></div>'
        f'<span>{changed_count:,} شاخص تغییریافته</span></div>'
        f'<div class="comparison-strip">{cards}</div>'
    )


def render_summary_cards(items: list[dict[str, str]], changed_count: int = 0) -> None:
    st.markdown(summary_cards_html(items, changed_count), unsafe_allow_html=True)


def indicator_cards_html(items: list[dict[str, str]]) -> str:
    cards = []
    for item in items:
        raw = item["raw"]
        rank = item["rank"]
        weighted = item["weighted"]
        cards.append(
            f'<article class="indicator-result-card {html.escape(item.get("tone", "neutral"))}">'
            f'<header><div class="indicator-title"><b aria-hidden="true">{html.escape(item["icon"])}</b><h3>{html.escape(item["name"])}</h3></div>'
            f'<div class="indicator-badges"><span class="weight-badge">وزن شاخص: {html.escape(item["weight"])}</span>'
            f'<span class="status-badge">{html.escape(item["status"])}</span></div></header>'
            '<section class="impact-section raw"><h4>مقایسه مقدار واقعی</h4><div class="impact-row four">'
            f'<div><span>مقدار فعلی</span><strong class="numeric-ltr" dir="ltr" title="{html.escape(raw.get("current_exact", raw["current"]))}">{html.escape(raw["current"])}</strong></div>'
            f'<div><span>مقدار سناریو</span><strong class="numeric-ltr" dir="ltr" title="{html.escape(raw.get("scenario_exact", raw["scenario"]))}">{html.escape(raw["scenario"])}</strong></div>'
            f'<div><span>تغییر مطلق</span><strong class="numeric-ltr" dir="ltr" title="{html.escape(raw.get("absolute_exact", raw["absolute"]))}">{html.escape(raw["absolute"])}</strong></div>'
            f'<div><span>تغییر درصدی</span><strong class="numeric-ltr" dir="ltr">{html.escape(raw["percent"])}</strong></div></div></section>'
            '<section class="impact-section rank-section"><h4>جایگاه شعبه در شاخص</h4><div class="rank-comparison">'
            f'<div><span>رتبه فعلی شعبه در شاخص</span><strong class="numeric-ltr" dir="ltr">رتبه {html.escape(rank["current"])}</strong></div>'
            f'<div><span>رتبه سناریوی شعبه در شاخص</span><strong class="numeric-ltr" dir="ltr">رتبه {html.escape(rank["scenario"])}</strong></div>'
            f'<div class="rank-result"><span>تغییر رتبه شاخص</span><strong>{html.escape(rank["change"])}</strong></div></div></section>'
            '<section class="impact-section weighted"><h4>امتیاز موزون و اثر نهایی</h4><div class="impact-row three">'
            f'<div><span>امتیاز موزون فعلی</span><strong class="numeric-ltr" dir="ltr">{html.escape(weighted["current"])}</strong></div>'
            f'<div><span>امتیاز موزون سناریو</span><strong class="numeric-ltr" dir="ltr">{html.escape(weighted["scenario"])}</strong></div>'
            f'<div class="overall-effect"><span>اثر بر امتیاز کل</span><strong class="numeric-ltr" dir="ltr">{html.escape(weighted["effect"])}</strong></div>'
            '</div></section></article>'
        )
    return f'<div class="indicator-result-grid">{"".join(cards)}</div>'


def render_indicator_cards(items: list[dict[str, str]]) -> None:
    st.markdown(indicator_cards_html(items), unsafe_allow_html=True)


def render_wizard_steps(labels: tuple[str, ...], current_step: int) -> None:
    cells = []
    for index, label in enumerate(labels, 1):
        state = "completed" if index < current_step else "active" if index == current_step else "future"
        number = persian_digits(index)
        cells.append(
            f'<div class="wizard-step wizard-step-{state} {"active" if state == "active" else ""}" data-step-state="{state}">'
            f'<span class="wizard-step-index" aria-hidden="true">{number}</span>'
            f'<span class="wizard-step-label">{number}. {html.escape(label)}</span></div>'
        )
        if index < len(labels):
            cells.append('<span class="wizard-connector" aria-hidden="true"></span>')
    st.markdown(f'<div class="wizard-steps" dir="rtl">{"".join(cells)}</div>', unsafe_allow_html=True)


def render_process_timeline(labels: tuple[str, ...]) -> None:
    content = " ← ".join(html.escape(label) for label in labels)
    st.markdown(f"<div class='process-line'>{content}</div>", unsafe_allow_html=True)
