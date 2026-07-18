"""Shared user-interface utilities."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

SESSION_DEFAULTS: dict[str, Any] = {
    "scenario_name": "",
    "selected_regions": [],
    "selected_branches": [],
    "scenario_changes": [],
    "scenario_dataframe": None,
    "scenario_results": None,
    "baseline_outputs": None,
    "scenario_outputs": None,
    "comparison_results": None,
    "scenario_executed": False,
    "current_scenario_id": None,
    "current_scenario_row_version": None,
    "current_scenario_dirty": False,
    "loaded_scenario_changes": [],
    "current_scenario_record": None,
    "indicator_editor_state": {},
    "loaded_scenario_edit_modes": {},
}


def initialize_session_state(
    state: MutableMapping[str, Any] | None = None,
) -> MutableMapping[str, Any]:
    """Initialize all cross-page keys once without overwriting existing values."""
    target = st.session_state if state is None else state
    for key, default in SESSION_DEFAULTS.items():
        if key not in target:
            target[key] = default.copy() if isinstance(default, list) else default
    return target


__all__ = ["SESSION_DEFAULTS", "initialize_session_state"]
