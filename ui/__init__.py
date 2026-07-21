"""Shared user-interface utilities."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

SESSION_DEFAULTS: dict[str, Any] = {
    "scenario_name": "",
    "selection_scope": "SELECTED_BRANCHES",
    "scenario_mode": "ONLY_USER_BRANCH",
    "focus_branch_id": None,
    "focus_branch_source": None,
    "selected_regions": [],
    "selected_branch_ids": [],
    "scenario_definition": {},
    "manual_override_rows": [],
    "manual_override_groups": [],
    "focus_branch_override_rows": [],
    "focus_branch_overrides": [],
    "branch_exception_groups": {},
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
    if "selected_branch_ids" not in target and "selected_branches" in target:
        target["selected_branch_ids"] = list(target["selected_branches"])
    for key, default in SESSION_DEFAULTS.items():
        if key not in target:
            target[key] = default.copy() if isinstance(default, list) else default
    target.pop("selected_branches", None)
    from ui.sensitivity_state import initialize_sensitivity_state

    initialize_sensitivity_state(target)
    return target


__all__ = ["SESSION_DEFAULTS", "initialize_session_state"]
