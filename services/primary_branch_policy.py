"""Primary-branch selection policy independent from UI and identity provider."""

from __future__ import annotations

from domain.multi_branch_contracts import ActorContext


class PrimaryBranchAuthorizationError(ValueError):
    pass


def resolve_primary_branch(
    actor: ActorContext, requested_branch_code: str | None
) -> str | None:
    """Resolve a selectable branch or enforce an identity-assigned branch."""
    requested = str(requested_branch_code).strip() if requested_branch_code is not None else None
    requested = requested or None
    assigned = (
        str(actor.assigned_branch_code).strip()
        if actor.assigned_branch_code is not None
        else None
    )
    assigned = assigned or None
    if actor.can_select_primary_branch:
        return requested
    if assigned is None:
        raise PrimaryBranchAuthorizationError("ASSIGNED_BRANCH_REQUIRED")
    if requested is not None and requested != assigned:
        raise PrimaryBranchAuthorizationError("PRIMARY_BRANCH_SELECTION_NOT_ALLOWED")
    return assigned
