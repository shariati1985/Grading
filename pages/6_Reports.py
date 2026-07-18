"""Reporting and export placeholder page."""

from __future__ import annotations

import streamlit as st

from ui import initialize_session_state
from ui.components import render_page_header
from ui.styles import apply_global_styles


def _report_placeholder(title: str, description: str) -> None:
    with st.container(border=True):
        st.subheader(title)
        st.write(description)
        st.button(f"تهیه {title}", key=f"report_{title}", disabled=True, width="stretch")


def main() -> None:
    initialize_session_state()
    apply_global_styles()
    render_page_header("گزارش‌ها", "خروجی‌های مدیریتی و فایل‌های قابل ارائه")
    left, right = st.columns(2)
    with left:
        _report_placeholder("خروجی Excel", "دریافت جداول نتایج و جزئیات شاخص‌ها در قالب Excel")
        _report_placeholder("گزارش سناریو", "گزارش کامل مشخصات و تغییرات سناریوی انتخاب‌شده")
    with right:
        _report_placeholder("خروجی PDF", "نسخه مدیریتی و قابل چاپ از نتایج تحلیل")
        _report_placeholder("گزارش اثر شبکه", "خلاصه تغییرات رتبه و درجه شعب در سطح شبکه")


main()
