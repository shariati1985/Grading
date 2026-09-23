"""Application-level data-scope contract independent from AD/HRM transport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

ScopeLevel = Literal["branch", "region", "head_office"]


@dataclass(frozen=True)
class OrganizationContext:
    """Normalized organizational placement supplied by the HRM integration."""

    user_id: str
    scope_level: ScopeLevel
    organization_reference: str | None = None


@dataclass(frozen=True)
class DataScope:
    """Resolved branch visibility for one authenticated user."""

    user_id: str
    scope_level: ScopeLevel
    permitted_branch_ids: tuple[str, ...]


def resolve_data_scope(
    context: OrganizationContext,
    *,
    own_branch_id: str | None = None,
    region_branch_ids: Iterable[str] | None = None,
    all_branch_ids: Iterable[str] | None = None,
) -> DataScope:
    """Resolve permitted branch IDs without coupling to HRM or database schemas.

    HRM determines only the normalized scope level/reference. Branch membership
    and hierarchy are supplied by the grading-dashboard database integration.
    """
    user_id = str(context.user_id).strip()
    if not user_id:
        raise ValueError("user_id is required")

    if context.scope_level == "branch":
        branch_id = "" if own_branch_id is None else str(own_branch_id).strip()
        if not branch_id:
            raise ValueError("branch scope requires own_branch_id")
        permitted = (branch_id,)

    elif context.scope_level == "region":
        values = tuple(dict.fromkeys(str(v).strip() for v in (region_branch_ids or ())))
        permitted = tuple(v for v in values if v)
        if not permitted:
            raise ValueError("region scope requires at least one subordinate branch")

    elif context.scope_level == "head_office":
        values = tuple(dict.fromkeys(str(v).strip() for v in (all_branch_ids or ())))
        permitted = tuple(v for v in values if v)
        if not permitted:
            raise ValueError("head_office scope requires the branch network")

    else:
        raise ValueError(f"Unsupported scope level: {context.scope_level!r}")

    return DataScope(
        user_id=user_id,
        scope_level=context.scope_level,
        permitted_branch_ids=permitted,
    )
