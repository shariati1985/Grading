"""Pure scenario selection-scope tests."""

from __future__ import annotations

import pandas as pd
import pytest

from services.selection_scope import (
    SelectionResolutionError,
    SelectionResolver,
    SelectionScope,
)
from services.user_context import CurrentUser
from services.user_context import load_current_user
from pathlib import Path
from ui.scenario_workflow import build_editor_data


@pytest.fixture
def branches() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "branch_id": ["103", "101", "102", "104", "102"],
            "branch_name": ["سه", "یک", "دو", "چهار", "دو تکراری"],
            "region": ["شمال", "مرکز", "جنوب", "شمال", "جنوب"],
            "is_active": [True, True, True, False, True],
        }
    )


def user(branch_id: str | None = None) -> CurrentUser:
    return CurrentUser("user", "کاربر", ("branch_user",), branch_id, "00101", "شعبه یک")


def test_selection_scope_has_exact_required_members() -> None:
    assert [item.name for item in SelectionScope] == [
        "USER_BRANCH",
        "SELECTED_BRANCHES",
        "SELECTED_REGIONS",
        "ALL_BRANCHES",
    ]


def test_user_branch_resolution(branches: pd.DataFrame) -> None:
    assert SelectionResolver.resolve(
        SelectionScope.USER_BRANCH, branches, user("101")
    ) == ["101"]


def test_missing_assigned_branch_is_rejected_in_persian(branches: pd.DataFrame) -> None:
    with pytest.raises(SelectionResolutionError, match="شعب منتخب"):
        SelectionResolver.resolve(SelectionScope.USER_BRANCH, branches, user())


def test_selected_branches_can_cross_regions_and_remove_duplicates(
    branches: pd.DataFrame,
) -> None:
    assert SelectionResolver.resolve(
        SelectionScope.SELECTED_BRANCHES,
        branches,
        user(),
        selected_branch_ids=["102", "101", "102"],
    ) == ["102", "101"]


def test_selected_regions_resolve_active_branches_deterministically(
    branches: pd.DataFrame,
) -> None:
    assert SelectionResolver.resolve(
        SelectionScope.SELECTED_REGIONS,
        branches,
        user(),
        selected_regions=["شمال", "جنوب", "شمال"],
    ) == ["103", "102"]


def test_all_branches_returns_active_deduplicated_baseline_order(
    branches: pd.DataFrame,
) -> None:
    assert SelectionResolver.resolve(
        SelectionScope.ALL_BRANCHES, branches, user()
    ) == ["103", "101", "102"]


@pytest.mark.parametrize(
    ("scope", "kwargs"),
    [
        (SelectionScope.SELECTED_BRANCHES, {"selected_branch_ids": []}),
        (SelectionScope.SELECTED_REGIONS, {"selected_regions": []}),
    ],
)
def test_empty_manual_selections_are_rejected(
    branches: pd.DataFrame, scope: SelectionScope, kwargs: dict[str, list[str]]
) -> None:
    with pytest.raises(SelectionResolutionError):
        SelectionResolver.resolve(scope, branches, user(), **kwargs)


def test_editor_receives_only_resolved_branch_ids(input_df: pd.DataFrame) -> None:
    requested = input_df.iloc[[2, 0]]["branch_id"].astype(str).tolist()
    resolved = SelectionResolver.resolve(
        SelectionScope.SELECTED_BRANCHES,
        input_df,
        user(),
        selected_branch_ids=requested,
    )
    editor = build_editor_data(input_df, resolved)
    assert editor["branch_id"].drop_duplicates().tolist() == resolved


def test_demo_user_branch_scope_resolves_only_zanjan(input_df: pd.DataFrame) -> None:
    root = Path(__file__).resolve().parents[1]
    demo_user = load_current_user(root / "config" / "local_user.json")
    resolved = SelectionResolver.resolve(
        SelectionScope.USER_BRANCH, input_df, demo_user
    )
    assert resolved == ["2001"]
    branch = input_df.loc[input_df["branch_id"].eq("2001")].iloc[0]
    assert branch["branch_name"] == "خیابان امام زنجان"
