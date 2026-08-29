from __future__ import annotations

from copy import deepcopy
import pytest
from persistence.sqlite_scenario_repository import SQLiteScenarioRepository
from services.scenario_management_service import ScenarioManagementService
from services.user_context import CurrentUser
from persistence.contracts import AuthorizationError, NotFoundError

from services.multi_branch_workspace_service import (
    MultiBranchWorkspaceService,
    normalize_multi_branch_scenario_name,
    restore_multi_branch_workspace,
    serialize_multi_branch_workspace,
)
def _workspace():
    workspace = dict(
        scenario_name="سناریوی دمو شبکه",
        period="1404-04",
        primary_branch_code="2001",
        current_stage="review",
        general_rules=[
            {"indicator_key": "resources", "direction": "increase", "percentage": 10.0}
        ],
        branch_exceptions={
            "2002": [
                {"indicator_key": "resources", "direction": "decrease", "percentage": 5.0}
            ]
        },
        primary_branch_overrides={
            "profit_loss": {
                "input_mode": "final",
                "input_value": 120.0,
                "resolved_raw_value": 120.0,
            }
        },
        execution_result=None,
        show_result=False,
    )
    return workspace


def test_multi_branch_definition_round_trip_preserves_editable_rules():
    original = _workspace()
    definition = serialize_multi_branch_workspace(original)
    restored, warnings = restore_multi_branch_workspace(
        definition, branch_ids=["2001", "2002"]
    )
    assert warnings == ()
    assert serialize_multi_branch_workspace(restored) == definition
    assert restored["execution_result"] is None
    assert restored["show_result"] is False


def test_definition_is_detached_from_live_workspace():
    workspace = _workspace()
    definition = serialize_multi_branch_workspace(workspace)
    workspace["general_rules"][0]["percentage"] = 99
    assert definition["general_rules"][0]["percentage"] == 10


def test_restore_drops_unknown_exception_branch_and_primary():
    definition = serialize_multi_branch_workspace(_workspace())
    restored, warnings = restore_multi_branch_workspace(
        deepcopy(definition), branch_ids=["9999"]
    )
    assert restored["primary_branch_code"] is None
    assert restored["branch_exceptions"] == {}
    assert len(warnings) == 2


def test_draft_load_update_and_new_version_lifecycle(tmp_path):
    management = ScenarioManagementService(
        SQLiteScenarioRepository(tmp_path / "multi-branch.db"),
        CurrentUser("u-demo", "کاربر دمو", ("staff",)),
    )
    service = MultiBranchWorkspaceService(management)
    workspace = _workspace()

    created = service.save_draft(workspace)
    loaded = service.load(created.scenario_id, branch_ids=["2001", "2002"])
    loaded.workspace["general_rules"][0]["percentage"] = 12.0
    assert service.has_unsaved_changes(loaded.workspace)

    updated = service.save_draft(loaded.workspace)
    version = service.save_draft(loaded.workspace, save_as_new=True)

    assert updated.scenario_id == created.scenario_id
    assert updated.row_version == 2
    assert version.scenario_id == created.scenario_id
    assert version.summary["phase3b_lineage"]["version_number"] == 2
    assert version.summary["phase3b_lineage"]["parent_scenario_id"] == created.scenario_id
    assert [item.scenario_id for item in management.list_visible(limit=25)] == [created.scenario_id]


def test_repeated_multi_branch_save_upserts_same_logical_scenario(tmp_path):
    management = ScenarioManagementService(
        SQLiteScenarioRepository(tmp_path / "multi-branch-upsert.db"),
        CurrentUser("u-demo", "کاربر دمو", ("staff",)),
    )
    service = MultiBranchWorkspaceService(management)
    first_workspace = _workspace()
    first = service.save_draft(first_workspace)
    second_workspace = _workspace()
    second_workspace["general_rules"][0]["percentage"] = 12.0

    second = service.save_draft(second_workspace)
    third = service.save_draft(second_workspace)

    assert second.scenario_id == first.scenario_id
    assert third.scenario_id == first.scenario_id
    assert third.row_version == 3
    assert [item.scenario_id for item in management.list_visible(limit=25)] == [first.scenario_id]


def test_multi_branch_save_as_new_increments_version_without_new_archive_card(tmp_path):
    management = ScenarioManagementService(
        SQLiteScenarioRepository(tmp_path / "multi-branch-version-upsert.db"),
        CurrentUser("u-demo", "کاربر دمو", ("staff",)),
    )
    service = MultiBranchWorkspaceService(management)
    workspace = _workspace()

    first = service.save_draft(workspace)
    second = service.save_draft(workspace, save_as_new=True)

    visible = management.list_visible(limit=25)
    assert second.scenario_id == first.scenario_id
    assert second.summary["phase3b_lineage"]["version_number"] == 2
    assert [item.scenario_id for item in visible] == [first.scenario_id]


def test_multi_branch_identity_separates_primary_branch_and_name(tmp_path):
    management = ScenarioManagementService(
        SQLiteScenarioRepository(tmp_path / "multi-branch-identity.db"),
        CurrentUser("u-demo", "کاربر دمو", ("staff",)),
    )
    service = MultiBranchWorkspaceService(management)
    first = service.save_draft(_workspace())
    second_workspace = _workspace()
    second_workspace["primary_branch_code"] = "2002"
    second = service.save_draft(second_workspace)
    third_workspace = _workspace()
    third_workspace["scenario_name"] = "سناریوی دیگر"
    third = service.save_draft(third_workspace)

    assert len({item.scenario_id for item in (first, second, third)}) == 3
    assert len(management.list_visible(limit=25)) == 3


def test_multi_branch_identity_isolated_by_user(tmp_path):
    repository = SQLiteScenarioRepository(tmp_path / "multi-branch-users.db")
    first = MultiBranchWorkspaceService(
        ScenarioManagementService(repository, CurrentUser("u-one", "کاربر یک", ("staff",)))
    )
    second = MultiBranchWorkspaceService(
        ScenarioManagementService(repository, CurrentUser("u-two", "کاربر دو", ("staff",)))
    )

    one = first.save_draft(_workspace())
    two = second.save_draft(_workspace())

    assert one.scenario_id != two.scenario_id
    assert len(first.management.list_visible(limit=25)) == 1
    assert len(second.management.list_visible(limit=25)) == 1


def test_multi_branch_name_normalization_prevents_whitespace_and_arabic_duplicates(tmp_path):
    management = ScenarioManagementService(
        SQLiteScenarioRepository(tmp_path / "multi-branch-normalized.db"),
        CurrentUser("u-demo", "کاربر دمو", ("staff",)),
    )
    service = MultiBranchWorkspaceService(management)
    first_workspace = _workspace()
    first_workspace["scenario_name"] = " سناریوی   كاربردی "
    second_workspace = _workspace()
    second_workspace["scenario_name"] = "سناریوی کاربردی"

    first = service.save_draft(first_workspace)
    second = service.save_draft(second_workspace)

    assert normalize_multi_branch_scenario_name(first_workspace["scenario_name"]) == normalize_multi_branch_scenario_name(second_workspace["scenario_name"])
    assert second.scenario_id == first.scenario_id
    assert len(management.list_visible(limit=25)) == 1


def test_saved_multi_branch_scenario_is_visible_in_archive_query(tmp_path):
    management = ScenarioManagementService(
        SQLiteScenarioRepository(tmp_path / "multi-branch-archive.db"),
        CurrentUser("u-demo", "کاربر دمو", ("staff",)),
    )
    service = MultiBranchWorkspaceService(management)
    workspace = _workspace()

    created = service.save_draft(workspace)
    visible = management.list_visible(limit=25)

    assert [item.scenario_id for item in visible] == [created.scenario_id]
    assert visible[0].summary["scenario_type"] == "MULTI_BRANCH_V1"
    assert visible[0].owner_user_id == "u-demo"
    assert visible[0].summary["multi_branch_definition"]["primary_branch_code"] == "2001"


def test_reopen_restores_multi_branch_inputs_and_result_metadata(tmp_path):
    management = ScenarioManagementService(
        SQLiteScenarioRepository(tmp_path / "multi-branch-restore.db"),
        CurrentUser("u-demo", "کاربر دمو", ("staff",)),
    )
    service = MultiBranchWorkspaceService(management)
    created = service.save_draft(_workspace())

    loaded = service.load(created.scenario_id, branch_ids=["2001", "2002"])

    assert loaded.workspace["general_rules"] == _workspace()["general_rules"]
    assert loaded.workspace["branch_exceptions"] == _workspace()["branch_exceptions"]
    assert loaded.workspace["primary_branch_overrides"] == _workspace()["primary_branch_overrides"]
    assert loaded.workspace["persistence"]["scenario_id"] == created.scenario_id
    assert loaded.workspace["entry_source"] == "saved"


def test_same_exception_indicator_on_different_branches_survives_reopen(tmp_path):
    management = ScenarioManagementService(
        SQLiteScenarioRepository(tmp_path / "multi-branch-pairs.db"),
        CurrentUser("u-demo", "کاربر دمو", ("staff",)),
    )
    service = MultiBranchWorkspaceService(management)
    workspace = _workspace()
    workspace["branch_exceptions"] = {
        "2001": [
            {"indicator_key": "avg_loans", "direction": "increase", "percentage": 10.0}
        ],
        "2002": [
            {"indicator_key": "avg_loans", "direction": "decrease", "percentage": 5.0}
        ],
    }

    created = service.save_draft(workspace)
    loaded = service.load(created.scenario_id, branch_ids=["2001", "2002"])

    assert loaded.workspace["branch_exceptions"] == workspace["branch_exceptions"]


def test_multi_branch_saved_scenario_can_be_deleted_and_reopen_fails(tmp_path):
    management = ScenarioManagementService(
        SQLiteScenarioRepository(tmp_path / "multi-branch-delete.db"),
        CurrentUser("u-demo", "کاربر دمو", ("staff",)),
    )
    service = MultiBranchWorkspaceService(management)
    saved = service.save_draft(_workspace())

    service.delete_scenario(saved.scenario_id, saved.row_version)

    assert management.list_visible(limit=25) == []
    with pytest.raises(NotFoundError):
        service.load(saved.scenario_id, branch_ids=["2001", "2002"])


def test_multi_branch_delete_rejects_unauthorized_user(tmp_path):
    repository = SQLiteScenarioRepository(tmp_path / "multi-branch-delete-auth.db")
    owner = MultiBranchWorkspaceService(
        ScenarioManagementService(repository, CurrentUser("u-owner", "مالک", ("staff",)))
    )
    other = MultiBranchWorkspaceService(
        ScenarioManagementService(repository, CurrentUser("u-other", "دیگری", ("staff",)))
    )
    saved = owner.save_draft(_workspace())

    with pytest.raises(AuthorizationError):
        other.delete_scenario(saved.scenario_id, saved.row_version)
