"""Pure branch-selection scope resolution for scenario editing."""

from __future__ import annotations

from enum import Enum

import pandas as pd

from engine.ranking_engine import BRANCH_ID, REGION
from services.user_context import CurrentUser


class SelectionScope(str, Enum):
    USER_BRANCH = "USER_BRANCH"
    SELECTED_BRANCHES = "SELECTED_BRANCHES"
    SELECTED_REGIONS = "SELECTED_REGIONS"
    ALL_BRANCHES = "ALL_BRANCHES"


class SelectionResolutionError(ValueError):
    """Raised when a scope cannot resolve to at least one active branch."""


class SelectionResolver:
    """Resolve selection inputs without UI, persistence, or model calculations."""

    @staticmethod
    def _active_branches(baseline_df: pd.DataFrame) -> pd.DataFrame:
        required = {BRANCH_ID, REGION}
        missing = required - set(baseline_df.columns)
        if missing:
            raise SelectionResolutionError(
                f"Missing selection columns: {', '.join(sorted(missing))}"
            )
        active = baseline_df
        if "is_active" in active.columns:
            active = active.loc[active["is_active"].fillna(False).astype(bool)]
        return active

    @classmethod
    def resolve(
        cls,
        scope: SelectionScope,
        baseline_df: pd.DataFrame,
        current_user: CurrentUser,
        *,
        selected_branch_ids: list[str] | None = None,
        selected_regions: list[str] | None = None,
    ) -> list[str]:
        if not isinstance(scope, SelectionScope):
            raise SelectionResolutionError("Selection scope is invalid")
        active = cls._active_branches(baseline_df)
        active_ids = list(dict.fromkeys(active[BRANCH_ID].astype(str).tolist()))
        active_id_set = set(active_ids)

        if scope is SelectionScope.USER_BRANCH:
            branch_id = (current_user.branch_id or "").strip()
            if not branch_id:
                raise SelectionResolutionError(
                    "شعبه‌ای به کاربر تخصیص داده نشده است؛ لطفاً از «شعب منتخب» استفاده کنید."
                )
            resolved = [branch_id] if branch_id in active_id_set else []
        elif scope is SelectionScope.SELECTED_BRANCHES:
            requested = list(dict.fromkeys(str(item) for item in selected_branch_ids or []))
            unknown = [item for item in requested if item not in active_id_set]
            if unknown:
                raise SelectionResolutionError(
                    "شناسه شعبه نامعتبر است: " + ", ".join(unknown)
                )
            resolved = requested
        elif scope is SelectionScope.SELECTED_REGIONS:
            regions = list(dict.fromkeys(str(item) for item in selected_regions or []))
            known_regions = set(active[REGION].astype(str))
            unknown = [item for item in regions if item not in known_regions]
            if unknown:
                raise SelectionResolutionError("منطقه نامعتبر است: " + ", ".join(unknown))
            region_set = set(regions)
            resolved = list(
                dict.fromkeys(
                    active.loc[active[REGION].astype(str).isin(region_set), BRANCH_ID]
                    .astype(str)
                    .tolist()
                )
            )
        else:
            resolved = active_ids

        if not resolved:
            raise SelectionResolutionError("حداقل یک شعبه فعال باید انتخاب شود.")
        return resolved
