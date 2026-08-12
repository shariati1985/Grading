"""Dedicated state namespace for the multi-branch workflow."""

from __future__ import annotations

from collections.abc import MutableMapping
from copy import deepcopy
from enum import Enum
from typing import Any


MULTI_BRANCH_STATE_KEY = "multi_branch_workspace"


class MultiBranchStage(str, Enum):
    """Fixed data-entry order for the dedicated multi-branch workspace."""

    SCENARIO_DETAILS = "scenario_details"
    GENERAL_RULES = "general_rules"
    BRANCH_EXCEPTIONS = "branch_exceptions"
    PRIMARY_BRANCH_OVERRIDES = "primary_branch_overrides"
    REVIEW = "review"


MULTI_BRANCH_STAGE_ORDER = (
    MultiBranchStage.SCENARIO_DETAILS,
    MultiBranchStage.GENERAL_RULES,
    MultiBranchStage.BRANCH_EXCEPTIONS,
    MultiBranchStage.PRIMARY_BRANCH_OVERRIDES,
    MultiBranchStage.REVIEW,
)

MULTI_BRANCH_STAGE_LABELS = {
    MultiBranchStage.SCENARIO_DETAILS: "مشخصات سناریو",
    MultiBranchStage.GENERAL_RULES: "قواعد عمومی",
    MultiBranchStage.BRANCH_EXCEPTIONS: "استثناهای شعب",
    MultiBranchStage.PRIMARY_BRANCH_OVERRIDES: "مقادیر شعبه اصلی",
    MultiBranchStage.REVIEW: "بازبینی و اجرا",
}


def new_multi_branch_workspace() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "current_stage": MultiBranchStage.SCENARIO_DETAILS.value,
        "scenario_name": "",
        "period": "1404-04",
        "primary_branch_code": None,
        "general_rules": [],
        "branch_exceptions": {},
        "primary_branch_overrides": {},
        "validation_errors": [],
        "preview": None,
        "execution_result": None,
        "show_result": False,
    }


def current_multi_branch_stage(workspace: dict[str, Any]) -> MultiBranchStage:
    value = workspace.get("current_stage", MultiBranchStage.SCENARIO_DETAILS.value)
    try:
        return MultiBranchStage(value)
    except ValueError as exc:
        raise ValueError(f"Unknown multi-branch stage: {value}") from exc


def move_to_multi_branch_stage(
    workspace: dict[str, Any], target: MultiBranchStage
) -> None:
    """Move through the fixed workflow without skipping an unfinished stage."""
    current = current_multi_branch_stage(workspace)
    current_index = MULTI_BRANCH_STAGE_ORDER.index(current)
    target_index = MULTI_BRANCH_STAGE_ORDER.index(target)
    if target_index > current_index + 1:
        raise ValueError("مراحل ورود اطلاعات سناریو باید به‌ترتیب تکمیل شوند.")
    workspace["current_stage"] = target.value
    invalidate_multi_branch_result(workspace)


def initialize_multi_branch_state(state: MutableMapping[str, Any]) -> dict[str, Any]:
    state.setdefault(MULTI_BRANCH_STATE_KEY, new_multi_branch_workspace())
    return state[MULTI_BRANCH_STATE_KEY]


def reset_multi_branch_state(state: MutableMapping[str, Any]) -> dict[str, Any]:
    state[MULTI_BRANCH_STATE_KEY] = new_multi_branch_workspace()
    return state[MULTI_BRANCH_STATE_KEY]


def copy_multi_branch_workspace(state: MutableMapping[str, Any]) -> dict[str, Any]:
    return deepcopy(initialize_multi_branch_state(state))


def invalidate_multi_branch_result(workspace: dict[str, Any]) -> None:
    workspace["validation_errors"] = []
    workspace["preview"] = None
    workspace["execution_result"] = None
    workspace["show_result"] = False
