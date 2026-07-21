"""Controlled, session-scoped state for the sensitivity wizard."""

from __future__ import annotations

from collections.abc import MutableMapping
from copy import deepcopy
from typing import Any

from domain.scenario_contracts import ScenarioType

SENSITIVITY_DRAFT_KEY = "sensitivity_draft"
SESSION_HISTORY_KEY = "sensitivity_session_history"


def new_scenario_draft(mode: ScenarioType | None = None) -> dict[str, Any]:
    return {
        "scenario_type": mode,
        "current_step": 1,
        "period": "1404-04",
        "scenario_name": "",
        "focus_branch_id": None,
        "focus_branch_source": None,
        "selected_branch_ids": [],
        "selected_indicator_ids": [],
        "focus_changes": {},
        "bulk_rules": [],
        "manual_overrides": [],
        "target_rank_request": {},
        "validation_errors": [],
        "execution_result": None,
        "target_solution": None,
        "show_result": False,
        "execute_requested": False,
        "persistence": {},
        "persisted_result_summaries": [],
        "entry_source": "new",
    }


def initialize_sensitivity_state(state: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    state.setdefault(SENSITIVITY_DRAFT_KEY, new_scenario_draft())
    state.setdefault(SESSION_HISTORY_KEY, [])
    return state


def switch_scenario_mode(state: MutableMapping[str, Any], mode: ScenarioType) -> dict[str, Any]:
    initialize_sensitivity_state(state)
    current = state[SENSITIVITY_DRAFT_KEY]
    if current.get("scenario_type") is not mode:
        state[SENSITIVITY_DRAFT_KEY] = new_scenario_draft(mode)
    return state[SENSITIVITY_DRAFT_KEY]


def start_new_scenario(state: MutableMapping[str, Any], mode: ScenarioType) -> dict[str, Any]:
    """Start a clean wizard even when the requested mode matches the old draft."""
    initialize_sensitivity_state(state)
    state[SENSITIVITY_DRAFT_KEY] = new_scenario_draft(mode)
    for key in list(state):
        text = str(key)
        if text in {"sensitivity_focus_branch", "official_result_branch"} or text.startswith(
            ("select_FOCUS_BRANCH_ONLY_", "focus_op_", "focus_value_", "focus_direction_")
        ):
            state.pop(key, None)
    return state[SENSITIVITY_DRAFT_KEY]


def set_focus_branch(draft: dict[str, Any], branch_id: str | None, source: str | None = None) -> None:
    normalized = str(branch_id) if branch_id is not None else None
    if draft.get("focus_branch_id") != normalized:
        draft["focus_branch_id"] = normalized
        draft["focus_branch_source"] = source
        draft["selected_indicator_ids"] = []
        draft["focus_changes"] = {}
        draft["manual_overrides"] = []
        draft["target_rank_request"] = {}
        draft["execution_result"] = None
        draft["target_solution"] = None
        draft["show_result"] = False


def set_multi_branch_selection(
    draft: dict[str, Any], branch_ids: list[str], *, focus_source: str | None = None
) -> None:
    """Store a unique multi-branch selection and use its first branch as focus."""
    selected = list(dict.fromkeys(map(str, branch_ids)))
    focus = selected[0] if selected else None
    if draft.get("focus_branch_id") != focus:
        set_focus_branch(draft, focus, focus_source if focus else None)
    if draft.get("selected_branch_ids") != selected:
        draft["selected_branch_ids"] = selected
        invalidate_computed_result(draft)


def invalidate_computed_result(draft: dict[str, Any]) -> None:
    """Discard backend output after any request-defining input changes."""
    draft["execution_result"] = None
    draft["target_solution"] = None
    draft["show_result"] = False
    draft["execute_requested"] = False


def set_period(draft: dict[str, Any], period: str) -> None:
    normalized = str(period).strip()
    if draft.get("period") != normalized:
        mode = draft.get("scenario_type")
        draft.clear()
        draft.update(new_scenario_draft(mode))
        draft["period"] = normalized


def set_selected_indicators(draft: dict[str, Any], indicator_ids: list[str]) -> None:
    selected = list(dict.fromkeys(map(str, indicator_ids)))
    if selected != draft.get("selected_indicator_ids", []):
        draft["selected_indicator_ids"] = selected
        draft["focus_changes"] = {
            key: value for key, value in draft.get("focus_changes", {}).items()
            if key in selected
        }
        invalidate_computed_result(draft)


def delete_bulk_rule(draft: dict[str, Any], index: int) -> None:
    draft["bulk_rules"].pop(index)
    invalidate_computed_result(draft)


def delete_manual_override(draft: dict[str, Any], index: int) -> None:
    draft["manual_overrides"].pop(index)
    invalidate_computed_result(draft)


def return_to_edit(draft: dict[str, Any]) -> None:
    invalidate_computed_result(draft)


def reset_sensitivity_draft(state: MutableMapping[str, Any]) -> None:
    initialize_sensitivity_state(state)
    mode = state[SENSITIVITY_DRAFT_KEY].get("scenario_type")
    state[SENSITIVITY_DRAFT_KEY] = new_scenario_draft(mode)


def copy_sensitivity_draft(state: MutableMapping[str, Any]) -> dict[str, Any]:
    initialize_sensitivity_state(state)
    copied = deepcopy(state[SENSITIVITY_DRAFT_KEY])
    copied["execution_result"] = None
    copied["target_solution"] = None
    copied["show_result"] = False
    copied["current_step"] = 4
    state[SENSITIVITY_DRAFT_KEY] = copied
    return copied
