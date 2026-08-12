from datetime import datetime, timezone

import pandas as pd
import pytest

from domain.multi_branch_contracts import (
    ActorContext,
    ActorScope,
    BranchException,
    EffectiveChangeSource,
    MultiBranchScenarioV1,
    PercentageDirection,
    PercentageRule,
    PopulationDefinition,
    PrimaryBranchOverride,
)
from engine.indicator_registry import INDICATOR_REGISTRY
from services.multi_branch_rule_resolver import (
    MultiBranchRuleResolver,
    MultiBranchRuleValidationError,
)


def _baseline() -> pd.DataFrame:
    rows = []
    for branch_id, multiplier in (("101", 1.0), ("202", 2.0), ("303", 3.0)):
        row = {"branch_id": branch_id, "branch_name": f"شعبه {branch_id}"}
        row.update({key: 100.0 * multiplier for key in INDICATOR_REGISTRY})
        row["profit_loss"] = -100.0 * multiplier
        rows.append(row)
    return pd.DataFrame(rows)


def _scenario(**changes) -> MultiBranchScenarioV1:
    now = datetime.now(timezone.utc)
    values = dict(
        scenario_id="s-1",
        scenario_name="سناریوی شبکه",
        created_at=now,
        updated_at=now,
        actor_context=ActorContext("u-1", ActorScope.STAFF),
        primary_branch_code="101",
        population_definition=PopulationDefinition("official-eligible-v1", expected_branch_count=3),
    )
    values.update(changes)
    return MultiBranchScenarioV1(**values)


def _manifest(result, branch, indicator):
    return next(
        item for item in result.manifest
        if item.branch_code == branch and item.indicator_key == indicator
    )


def test_precedence_is_resolved_per_branch_and_indicator_across_all_eight_indicators() -> None:
    all_general = tuple(
        PercentageRule(key, PercentageDirection.INCREASE, 10.0)
        for key in INDICATOR_REGISTRY
    )
    scenario = _scenario(
        general_rules=all_general,
        branch_exceptions=(
            BranchException("101", (PercentageRule("avg_deposits", PercentageDirection.INCREASE, 40.0),)),
            BranchException("202", (PercentageRule("avg_deposits", PercentageDirection.INCREASE, 25.0),)),
        ),
        primary_branch_overrides=(
            PrimaryBranchOverride("avg_deposits", "SET_VALUE", 175.0, 175.0),
        ),
    )

    result = MultiBranchRuleResolver.resolve(scenario, _baseline())

    assert _manifest(result, "101", "avg_deposits").scenario_value == 175.0
    assert _manifest(result, "101", "avg_deposits").effective_source is EffectiveChangeSource.PRIMARY_EXPLICIT
    assert _manifest(result, "202", "avg_deposits").scenario_value == 250.0
    assert _manifest(result, "202", "avg_deposits").effective_source is EffectiveChangeSource.BRANCH_EXCEPTION
    assert _manifest(result, "303", "avg_deposits").scenario_value == pytest.approx(330.0)
    assert _manifest(result, "303", "avg_deposits").effective_source is EffectiveChangeSource.GENERAL_RULE
    assert len(result.manifest) == 3 * 8


def test_exception_only_replaces_same_indicator_and_is_not_cumulative() -> None:
    scenario = _scenario(
        general_rules=(
            PercentageRule("avg_deposits", PercentageDirection.INCREASE, 30.0),
            PercentageRule("avg_loans", PercentageDirection.INCREASE, 20.0),
        ),
        branch_exceptions=(
            BranchException("202", (PercentageRule("avg_deposits", PercentageDirection.INCREASE, 45.0),)),
        ),
    )
    result = MultiBranchRuleResolver.resolve(scenario, _baseline())
    assert _manifest(result, "202", "avg_deposits").scenario_value == pytest.approx(290.0)
    assert _manifest(result, "202", "avg_loans").scenario_value == pytest.approx(240.0)


def test_signed_profit_loss_uses_raw_percentage_formula() -> None:
    scenario = _scenario(
        general_rules=(PercentageRule("profit_loss", PercentageDirection.INCREASE, 10.0),)
    )
    result = MultiBranchRuleResolver.resolve(scenario, _baseline())
    assert _manifest(result, "101", "profit_loss").scenario_value == pytest.approx(-110.0)


def test_decrease_above_one_hundred_is_rejected_when_final_value_breaks_indicator_domain() -> None:
    scenario = _scenario(
        general_rules=(PercentageRule("avg_deposits", PercentageDirection.DECREASE, 110.0),)
    )
    with pytest.raises(MultiBranchRuleValidationError) as error:
        MultiBranchRuleResolver.resolve(scenario, _baseline())
    assert "BELOW_MINIMUM" in error.value.issues[0]


def test_population_mismatch_prevents_silent_ranking_universe_drop() -> None:
    scenario = _scenario(
        population_definition=PopulationDefinition("official-eligible-v1", expected_branch_count=223)
    )
    with pytest.raises(MultiBranchRuleValidationError) as error:
        MultiBranchRuleResolver.resolve(scenario, _baseline())
    assert "POPULATION_COUNT_MISMATCH" in error.value.issues
