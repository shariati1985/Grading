"""Official indicator-rank coverage for Branch-Centric result cards."""

from __future__ import annotations

import pandas as pd
import pytest

from domain.scenario_contracts import IndicatorChange, ScenarioRequest, ScenarioType
from engine.ranking_engine import INDICATOR_KEYS, run_ranking_model
from engine.scenario_rule_engine import RuleOperation
from services.scenario_execution_service import ScenarioExecutionService
from ui.sensitivity_adapters import focus_result_presentation


def _population(values: list[float], indicator: str = "avg_deposits") -> pd.DataFrame:
    rows = []
    for index, (branch_id, name) in enumerate(zip(("101", "102", "103"), ("الف", "ب", "پ"))):
        row = {key: 100.0 + index for key in INDICATOR_KEYS}
        row.update(branch_id=branch_id, branch_name=name, region="آزمون")
        row[indicator] = values[index]
        rows.append(row)
    return pd.DataFrame(rows)


def _execute(data: pd.DataFrame, branch: str, indicator: str, value: float):
    request = ScenarioRequest(
        ScenarioType.FOCUS_BRANCH_ONLY, "رتبه شاخص", branch,
        focus_branch_changes=(IndicatorChange(indicator, RuleOperation.SET_VALUE, value),),
    )
    return ScenarioExecutionService().execute(request, data)


@pytest.mark.parametrize(
    ("branch", "scenario_value", "expected_current", "expected_scenario", "expected_text"),
    [
        ("101", 250.0, 3, 2, "۱ رتبه بهبود"),
        ("103", 150.0, 1, 2, "۱ رتبه افت"),
        ("102", 210.0, 2, 2, "بدون تغییر رتبه"),
    ],
)
def test_indicator_card_uses_official_improved_declined_and_unchanged_rank(
    branch, scenario_value, expected_current, expected_scenario, expected_text
) -> None:
    result = _execute(_population([100.0, 200.0, 300.0]), branch, "avg_deposits", scenario_value)
    _, cards = focus_result_presentation(result.focus_branch_comparison)
    rank = cards[0]["rank"]
    assert (int(rank["current"]), int(rank["scenario"]), rank["change"]) == (
        expected_current, expected_scenario, expected_text,
    )


def test_indicator_rank_tie_uses_official_branch_name_tiebreak() -> None:
    outputs = run_ranking_model(_population([200.0, 200.0, 300.0]))
    rows = outputs.indicator_results.query("indicator_key == 'avg_deposits'").set_index("branch_id")
    assert rows.loc["101", "score"] == pytest.approx(rows.loc["102", "score"])
    assert int(rows.loc["101", "indicator_rank"]) == 2
    assert int(rows.loc["102", "indicator_rank"]) == 3


def test_profit_loss_negative_values_keep_real_official_rank() -> None:
    result = _execute(_population([-300.0, -200.0, -100.0], "profit_loss"), "101", "profit_loss", -150.0)
    item = next(
        row for row in result.focus_branch_comparison.indicator_comparisons
        if row["indicator_key"] == "profit_loss"
    )
    _, cards = focus_result_presentation(result.focus_branch_comparison)
    assert item["baseline_raw_value"] == -300.0
    assert item["scenario_raw_value"] == -150.0
    assert (item["baseline_indicator_rank"], item["scenario_indicator_rank"]) == (3, 2)
    assert cards[0]["rank"]["change"] == "۱ رتبه بهبود"


def test_indicator_card_rank_matches_both_official_model_outputs() -> None:
    result = _execute(_population([100.0, 200.0, 300.0]), "101", "avg_deposits", 250.0)
    baseline = result.baseline_outputs.indicator_results.query(
        "branch_id == '101' and indicator_key == 'avg_deposits'"
    ).iloc[0]
    scenario = result.scenario_outputs.indicator_results.query(
        "branch_id == '101' and indicator_key == 'avg_deposits'"
    ).iloc[0]
    _, cards = focus_result_presentation(result.focus_branch_comparison)
    assert int(cards[0]["rank"]["current"]) == int(baseline["indicator_rank"])
    assert int(cards[0]["rank"]["scenario"]) == int(scenario["indicator_rank"])
