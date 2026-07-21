"""Small reusable renderers for the sensitivity workspace."""

from __future__ import annotations

import html

import streamlit as st


def render_wizard_steps(labels: tuple[str, ...], current_step: int) -> None:
    cells = "".join(
        f"<div class='wizard-step {'active' if index == current_step else ''}'>"
        f"{index}. {html.escape(label)}</div>"
        for index, label in enumerate(labels, 1)
    )
    st.markdown(f"<div class='wizard-steps'>{cells}</div>", unsafe_allow_html=True)


def render_process_timeline(labels: tuple[str, ...]) -> None:
    content = " ← ".join(html.escape(label) for label in labels)
    st.markdown(f"<div class='process-line'>{content}</div>", unsafe_allow_html=True)
