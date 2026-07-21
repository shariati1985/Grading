"""Auditable model diagnostics keyed strictly by branch identity."""

from __future__ import annotations

import pandas as pd

from engine.indicator_registry import PROFIT_LOSS_KEY
from engine.ranking_engine import BRANCH_ID, BRANCH_NAME, ModelOutputs, WEIGHTS


def build_profit_loss_diagnostics(
    baseline: ModelOutputs, scenario: ModelOutputs
) -> pd.DataFrame:
    """Return baseline/scenario Profit/Loss values and scores joined by branch_id."""
    baseline_indicator = baseline.indicator_results.loc[
        baseline.indicator_results["indicator_key"].eq(PROFIT_LOSS_KEY),
        [BRANCH_ID, BRANCH_NAME, "raw_value", "score", "weighted_score"],
    ].rename(
        columns={
            "raw_value": "raw_profit_loss",
            "score": "normalized_profit_loss_score",
            "weighted_score": "weighted_profit_loss_score",
        }
    )
    scenario_indicator = scenario.indicator_results.loc[
        scenario.indicator_results["indicator_key"].eq(PROFIT_LOSS_KEY),
        [BRANCH_ID, "raw_value", "score"],
    ].rename(
        columns={
            "raw_value": "scenario_profit_loss",
            "score": "displayed_profit_loss_score",
        }
    )
    result = baseline_indicator.merge(
        scenario_indicator, on=BRANCH_ID, how="inner", validate="one_to_one"
    ).merge(
        scenario.final_result[[BRANCH_ID, "final_score", "rank"]],
        on=BRANCH_ID,
        how="inner",
        validate="one_to_one",
    )
    result["branch_code"] = result[BRANCH_ID]
    result["raw_profit_loss_rank"] = result["raw_profit_loss"].rank(
        method="min", ascending=False
    ).astype(int)
    result["profit_loss_weight"] = WEIGHTS[PROFIT_LOSS_KEY]
    return result.rename(
        columns={"final_score": "overall_score", "rank": "overall_rank"}
    ).loc[
        :,
        [
            BRANCH_ID,
            "branch_code",
            BRANCH_NAME,
            "raw_profit_loss",
            "scenario_profit_loss",
            "raw_profit_loss_rank",
            "normalized_profit_loss_score",
            "weighted_profit_loss_score",
            "displayed_profit_loss_score",
            "profit_loss_weight",
            "overall_score",
            "overall_rank",
        ],
    ]
