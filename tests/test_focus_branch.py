"""Assigned and staff focus-branch model tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.focus_branch import (
    FocusBranchSource,
    resolve_focus_branch,
    scenario_mode_labels,
)
from services.user_context import CurrentUser, load_current_user


def test_branch_assigned_user_automatically_resolves_zanjan(input_df) -> None:
    root = Path(__file__).resolve().parents[1]
    user = load_current_user(root / "config" / "local_user.json")
    focus = resolve_focus_branch(user, input_df)
    assert focus is not None
    assert focus.branch_id == "2001"
    assert focus.source is FocusBranchSource.ASSIGNED_USER_BRANCH


def test_staff_user_is_not_blocked_and_can_select_any_active_branch(input_df) -> None:
    staff = CurrentUser("staff", "ستادی", ("staff_user",))
    assert resolve_focus_branch(staff, input_df) is None
    selected = str(input_df.iloc[-1]["branch_id"])
    focus = resolve_focus_branch(staff, input_df, selected_branch_id=selected)
    assert focus is not None
    assert focus.branch_id == selected
    assert focus.source is FocusBranchSource.USER_SELECTED_BRANCH


def test_branch_and_staff_mode_labels_are_distinct() -> None:
    branch_user = CurrentUser("branch", "شعبه", (), branch_id="2001")
    staff_user = CurrentUser("staff", "ستاد", ())
    assert list(scenario_mode_labels(branch_user).values()) == [
        "فقط شعبه من تغییر کند",
        "شعبه من و سایر شعب تغییر کنند",
    ]
    assert list(scenario_mode_labels(staff_user).values()) == [
        "فقط شعبه محوری تغییر کند",
        "شعبه محوری و سایر شعب تغییر کنند",
    ]


def test_persisted_staff_focus_survives_reruns(input_df) -> None:
    staff = CurrentUser("staff", "ستاد", ())
    first = resolve_focus_branch(staff, input_df, selected_branch_id="2001")
    restored = resolve_focus_branch(
        staff,
        input_df,
        persisted_branch_id=first.branch_id if first else None,
        persisted_source=first.source.value if first else None,
    )
    assert restored == first


def test_unavailable_persisted_focus_is_rejected(input_df) -> None:
    staff = CurrentUser("staff", "ستاد", ())
    with pytest.raises(ValueError, match="دیگر در فهرست شعب فعال"):
        resolve_focus_branch(
            staff,
            input_df,
            persisted_branch_id="missing",
            persisted_source="USER_SELECTED_BRANCH",
        )


def test_staff_fixture_has_no_assigned_branch() -> None:
    root = Path(__file__).resolve().parents[1]
    staff = load_current_user(root / "tests" / "fixtures" / "staff_user.json")
    assert staff.branch_id is None
    assert staff.branch_code is None
    assert staff.branch_name is None
