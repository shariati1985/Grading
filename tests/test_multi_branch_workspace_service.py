from __future__ import annotations

from copy import deepcopy
from persistence.sqlite_scenario_repository import SQLiteScenarioRepository
from services.scenario_management_service import ScenarioManagementService
from services.user_context import CurrentUser

from services.multi_branch_workspace_service import (
    MultiBranchWorkspaceService,
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
    assert version.scenario_id != created.scenario_id
    assert version.summary["phase3b_lineage"]["version_number"] == 2
    assert version.summary["phase3b_lineage"]["parent_scenario_id"] == created.scenario_id
