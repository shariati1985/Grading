"""Tests for the agreed organizational Data Scope rules."""

import pytest

from services.access_scope import OrganizationContext, resolve_data_scope


def test_branch_user_sees_only_own_branch():
    scope = resolve_data_scope(
        OrganizationContext("u1", "branch", "branch-103"),
        own_branch_id="103",
    )
    assert scope.permitted_branch_ids == ("103",)


def test_region_user_sees_subordinate_branches_from_grading_hierarchy():
    scope = resolve_data_scope(
        OrganizationContext("u2", "region", "region-7"),
        region_branch_ids=["101", "102", "103", "102"],
    )
    assert scope.permitted_branch_ids == ("101", "102", "103")


def test_head_office_user_sees_entire_network():
    scope = resolve_data_scope(
        OrganizationContext("u3", "head_office", "hq"),
        all_branch_ids=["101", "102", "103"],
    )
    assert scope.permitted_branch_ids == ("101", "102", "103")


def test_region_scope_fails_without_hierarchy_result():
    with pytest.raises(ValueError, match="at least one subordinate branch"):
        resolve_data_scope(
            OrganizationContext("u2", "region", "region-7"),
            region_branch_ids=[],
        )
