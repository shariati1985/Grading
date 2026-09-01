import pytest

from domain.multi_branch_contracts import ActorContext, ActorScope
from services.primary_branch_policy import (
    PrimaryBranchAuthorizationError,
    resolve_primary_branch,
)


def test_head_office_actor_can_select_primary_branch() -> None:
    actor = ActorContext("staff-1", ActorScope.HEAD_OFFICE, can_select_primary_branch=True)
    assert resolve_primary_branch(actor, "202") == "202"


def test_future_branch_actor_uses_read_only_assigned_branch() -> None:
    actor = ActorContext(
        "branch-1",
        ActorScope.BRANCH,
        assigned_branch_code="101",
        can_select_primary_branch=False,
    )
    assert resolve_primary_branch(actor, None) == "101"
    with pytest.raises(PrimaryBranchAuthorizationError):
        resolve_primary_branch(actor, "202")
