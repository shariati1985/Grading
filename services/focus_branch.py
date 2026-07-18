"""Pure focus-branch resolution for assigned and staff users."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from engine.ranking_engine import BRANCH_ID
from services.user_context import CurrentUser


class FocusBranchSource(str, Enum):
    ASSIGNED_USER_BRANCH = "ASSIGNED_USER_BRANCH"
    USER_SELECTED_BRANCH = "USER_SELECTED_BRANCH"


@dataclass(frozen=True)
class FocusBranch:
    branch_id: str
    source: FocusBranchSource


def resolve_focus_branch(
    current_user: CurrentUser,
    baseline_df: pd.DataFrame,
    *,
    selected_branch_id: str | None = None,
    persisted_branch_id: str | None = None,
    persisted_source: str | None = None,
) -> FocusBranch | None:
    active_ids = set(baseline_df[BRANCH_ID].astype(str))
    if persisted_branch_id:
        branch_id = str(persisted_branch_id)
        if branch_id not in active_ids:
            raise ValueError("شعبه محوری ذخیره‌شده دیگر در فهرست شعب فعال وجود ندارد.")
        source = (
            FocusBranchSource(str(persisted_source))
            if persisted_source
            else FocusBranchSource.USER_SELECTED_BRANCH
        )
        return FocusBranch(branch_id, source)
    if current_user.branch_id:
        branch_id = str(current_user.branch_id)
        if branch_id not in active_ids:
            raise ValueError("شعبه تخصیص‌یافته کاربر در فهرست شعب فعال وجود ندارد.")
        return FocusBranch(branch_id, FocusBranchSource.ASSIGNED_USER_BRANCH)
    if not selected_branch_id:
        return None
    branch_id = str(selected_branch_id)
    if branch_id not in active_ids:
        raise ValueError("شعبه محوری انتخاب‌شده در فهرست شعب فعال وجود ندارد.")
    return FocusBranch(branch_id, FocusBranchSource.USER_SELECTED_BRANCH)


def scenario_mode_labels(current_user: CurrentUser) -> dict[str, str]:
    if current_user.branch_id:
        return {
            "ONLY_USER_BRANCH": "فقط شعبه من تغییر کند",
            "USER_AND_OTHERS": "شعبه من و سایر شعب تغییر کنند",
        }
    return {
        "ONLY_USER_BRANCH": "فقط شعبه محوری تغییر کند",
        "USER_AND_OTHERS": "شعبه محوری و سایر شعب تغییر کنند",
    }
