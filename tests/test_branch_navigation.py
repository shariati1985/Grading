"""Selected-branch selector navigation state tests."""

from ui.branch_navigation import adjacent_branch_id, retain_selected_branch


def test_all_selected_branches_are_reachable_in_order() -> None:
    branch_ids = ["103", "101", "202", "305"]
    visited = [branch_ids[0]]
    for _ in range(len(branch_ids) - 1):
        visited.append(adjacent_branch_id(branch_ids, visited[-1], step=1))
    assert visited == branch_ids


def test_previous_and_next_navigation_wrap_deterministically() -> None:
    branch_ids = ["101", "202", "303"]
    assert adjacent_branch_id(branch_ids, "202", step=-1) == "101"
    assert adjacent_branch_id(branch_ids, "202", step=1) == "303"
    assert adjacent_branch_id(branch_ids, "101", step=-1) == "303"
    assert adjacent_branch_id(branch_ids, "303", step=1) == "101"


def test_selected_branch_survives_rerun_when_still_available() -> None:
    assert retain_selected_branch(["101", "202", "303"], "202") == "202"
    assert retain_selected_branch(["101", "303"], "202") == "101"


def test_results_prefer_assigned_zanjan_branch() -> None:
    ordered = ["101", "2001", "303"]
    assert retain_selected_branch(ordered, "2001") == "2001"
