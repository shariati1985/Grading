from domain.multi_branch_contracts import ActorScope
from services.user_context import CurrentUser
from ui.multi_branch_page import _actor_context, _build_scenario
from ui.multi_branch_state import new_multi_branch_workspace


def test_branch_user_is_bound_to_assigned_primary_branch() -> None:
    user = CurrentUser("u-1", "کاربر شعبه", ("branch_user",), branch_id="101")

    actor = _actor_context(user)

    assert actor.actor_scope is ActorScope.BRANCH
    assert actor.assigned_branch_code == "101"
    assert actor.can_select_primary_branch is False


def test_real_actor_is_preserved_in_scenario_contract() -> None:
    user = CurrentUser("staff-7", "کاربر ستادی", ("staff",))
    actor = _actor_context(user)
    workspace = new_multi_branch_workspace()
    workspace.update(scenario_name="آزمون شبکه", primary_branch_code="202")

    scenario = _build_scenario(workspace, 223, actor)

    assert scenario.actor_context.actor_id == "staff-7"
    assert scenario.actor_context.actor_scope is ActorScope.HEAD_OFFICE
    assert scenario.primary_branch_code == "202"
