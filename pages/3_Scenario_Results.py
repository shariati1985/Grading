"""Prepared scenario status page."""

from __future__ import annotations

import streamlit as st

from engine.ranking_engine import BRANCH_ID, BRANCH_NAME, REGION
from ui import initialize_session_state
from ui.components import render_branch_identity, render_empty_state, render_page_header
from ui.styles import apply_global_styles


def main() -> None:
    initialize_session_state()
    apply_global_styles()
    render_page_header("نتایج سناریو", "مشاهده وضعیت سناریوی آماده‌شده")
    scenario_df = st.session_state["scenario_dataframe"]
    if scenario_df is None:
        render_empty_state("هنوز سناریویی آماده نشده است. ابتدا از صفحه «ساخت سناریو» یک سناریو بسازید.")
        return

    st.subheader(f"سناریو: {st.session_state['scenario_name']}")
    selected = scenario_df.loc[
        scenario_df[BRANCH_ID].isin(st.session_state["selected_branches"]),
        [BRANCH_ID, BRANCH_NAME, REGION],
    ]
    st.caption("شعب منتخب")
    for row in selected.itertuples(index=False):
        render_branch_identity(str(row.branch_id), str(row.branch_name), str(row.region))
    st.info("سناریو آماده است و در گام بعدی نتایج محاسباتی به این صفحه متصل خواهد شد.")


main()
