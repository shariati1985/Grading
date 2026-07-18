"""Landing page for the branch sensitivity-analysis platform."""

from __future__ import annotations

import streamlit as st

from ui import initialize_session_state
from ui.components import render_navigation_card, render_page_header
from ui.styles import apply_global_styles

st.set_page_config(
    page_title="پلتفرم تحلیل حساسیت درجه‌بندی شعب",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    """Render the lightweight application landing page."""
    initialize_session_state()
    apply_global_styles()
    render_page_header(
        "پلتفرم تحلیل حساسیت درجه‌بندی شعب",
        "تحلیل سناریوهای تغییر شاخص‌ها و مشاهده اثر آن بر رتبه، امتیاز و درجه شعب",
    )
    st.markdown(
        "این سامانه برای مشاهده وضعیت مبنا، ساخت سناریوهای تغییر شاخص‌های شعب و "
        "بررسی اثر آن‌ها بر شبکه طراحی شده است. برای شروع، یکی از بخش‌های زیر را انتخاب کنید."
    )

    cards = (
        ("داشبورد", "نمای کلی رتبه، امتیاز، درجه و پراکندگی شعب", "pages/1_Dashboard.py"),
        ("ساخت سناریو", "انتخاب شعب و ویرایش هشت شاخص مدل", "pages/2_Scenario_Builder.py"),
        ("نتایج سناریو", "مشاهده سناریوی آماده‌شده و نتایج آن", "pages/3_Scenario_Results.py"),
        ("اثر بر کل شبکه", "بررسی تغییرات رتبه و درجه در سطح شبکه", "pages/4_Network_Impact.py"),
        ("مقایسه سناریوها", "مقایسه سناریوهای ذخیره‌شده در نسخه‌های آینده", "pages/5_Scenario_Comparison.py"),
        ("گزارش‌ها", "خروجی‌های مدیریتی و گزارش‌های سناریو", "pages/6_Reports.py"),
    )
    for row_start in range(0, len(cards), 3):
        columns = st.columns(3)
        for column, (title, description, path) in zip(columns, cards[row_start : row_start + 3]):
            with column:
                render_navigation_card(title, description, path)


if __name__ == "__main__":
    main()
