"""Pure ordered branch-result navigation helpers."""

from __future__ import annotations


def retain_selected_branch(ordered_ids: list[str], current_id: str | None) -> str | None:
    if not ordered_ids:
        return None
    return current_id if current_id in ordered_ids else ordered_ids[0]


def adjacent_branch_id(
    ordered_ids: list[str], current_id: str, *, step: int
) -> str:
    if not ordered_ids or current_id not in ordered_ids:
        raise ValueError("Current branch must exist in ordered branch IDs")
    index = ordered_ids.index(current_id)
    return ordered_ids[(index + step) % len(ordered_ids)]
