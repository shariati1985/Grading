"""Network impact placeholder page."""

from __future__ import annotations

import streamlit as st

from ui import initialize_session_state
from ui.components import render_empty_state, render_page_header
from ui.styles import apply_global_styles


def main() -> None:
    initialize_session_state()
    apply_global_styles()
    render_page_header("اثر بر کل شبکه", "بررسی اثر سناریو بر رتبه، امتیاز و درجه کل شعب")
    if st.session_state["scenario_dataframe"] is None:
        render_empty_state("برای بررسی اثر شبکه، ابتدا یک سناریو در صفحه «ساخت سناریو» آماده کنید.")
        return
    with st.container(border=True):
        st.subheader(f"سناریوی فعال: {st.session_state['scenario_name']}")
        st.info("نمایش نتایج اثر بر کل شبکه در گام بعدی به موتور مقایسه متصل خواهد شد.")


main()
