"""Regression tests for the calculation-free dashboard data adapter."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from data.dashboard_contracts import BRANCH_INDICATOR_COLUMNS, BRANCH_SUMMARY_COLUMNS
from data.dashboard_repository import DashboardRepository
from engine.ranking_engine import INDICATOR_KEYS, WEIGHTS, run_ranking_model
from services.dashboard_service import DashboardService

PERIOD = "1404-04"


def _repository(input_df) -> tuple[DashboardRepository, object]:
    outputs = run_ranking_model(input_df)
    repository = DashboardRepository(
        outputs,
        PERIOD,
        period_label="1404/04",
        calculation_timestamp=datetime(2026, 7, 19, tzinfo=timezone.utc),
    )
    return repository, outputs


def test_dashboard_contract_has_canonical_columns_and_valid_engine_values(input_df) -> None:
    repository, _ = _repository(input_df)
    summary = repository.load_branch_summary()
    indicators = repository.load_branch_indicators()
    assert tuple(summary.columns) == BRANCH_SUMMARY_COLUMNS
    assert tuple(indicators.columns) == BRANCH_INDICATOR_COLUMNS
    assert indicators["normalized_score"].between(1, 1000).all()
    assert not indicators.duplicated(["branch_id", "period_id", "indicator_id"]).any()
    assert indicators.groupby(["branch_id", "period_id"]).size().eq(8).all()
    assert set(indicators["indicator_id"]) == set(INDICATOR_KEYS)


def test_weights_and_contributions_are_exact_engine_exposure(input_df) -> None:
    repository, outputs = _repository(input_df)
    indicators = repository.load_branch_indicators()
    definitions = repository.load_indicator_definitions().set_index("indicator_id")
    assert np.isclose(definitions["weight"].sum(), 1.0)
    assert definitions["weight"].to_dict() == WEIGHTS
    source = outputs.indicator_results.rename(
        columns={"indicator_key": "indicator_id", "score": "normalized_score",
                 "weighted_score": "weighted_contribution"}
    )
    joined = indicators.merge(
        source[["branch_id", "indicator_id", "normalized_score", "weighted_contribution"]],
        on=["branch_id", "indicator_id"], suffixes=("_dashboard", "_engine"),
        validate="one_to_one",
    )
    pd.testing.assert_series_equal(joined["normalized_score_dashboard"],
                                   joined["normalized_score_engine"], check_names=False)
    pd.testing.assert_series_equal(joined["weighted_contribution_dashboard"],
                                   joined["weighted_contribution_engine"], check_names=False)


def test_branch_and_indicator_contracts_join_for_every_record(input_df) -> None:
    repository, _ = _repository(input_df)
    summary = repository.load_branch_summary()
    indicators = repository.load_branch_indicators()
    joined = indicators.merge(
        summary[["branch_id", "branch_code", "period_id", "final_rank"]],
        on=["branch_id", "branch_code", "period_id"], how="left", validate="many_to_one",
    )
    assert len(joined) == len(indicators)
    assert joined["final_rank"].notna().all()


def test_fatemi_profit_loss_canonical_score_regression(input_df) -> None:
    repository, outputs = _repository(input_df)
    fatemi = repository.load_branch_indicators().loc[
        lambda frame: frame["branch_code"].eq("103")
        & frame["indicator_id"].eq("profit_loss")
    ].iloc[0]
    engine = outputs.indicator_results.loc[
        lambda frame: frame["branch_id"].eq("103")
        & frame["indicator_key"].eq("profit_loss")
    ].iloc[0]
    assert fatemi["normalized_score"] == pytest.approx(856.7019931, abs=1e-6)
    assert fatemi["shifted_value"] == engine["shifted_value"]
    assert fatemi["log_value"] == engine["log_value"]
    assert fatemi["normalized_score"] == engine["score"]
    assert fatemi["weighted_contribution"] == engine["weighted_score"]
    assert fatemi["indicator_rank"] == 222


def test_dashboard_service_only_filters_canonical_rows(input_df) -> None:
    repository, _ = _repository(input_df)
    service = DashboardService(repository)
    expected = repository.load_branch_indicators().loc[
        lambda frame: frame["branch_id"].eq("103") & frame["period_id"].eq(PERIOD)
    ].reset_index(drop=True)
    pd.testing.assert_frame_equal(service.get_branch_indicators("103", PERIOD), expected)
    assert len(service.get_branch_indicator("103", "profit_loss", PERIOD)) == 1
    assert service.get_branch_ranking(PERIOD)["final_rank"].is_monotonic_increasing
    assert service.get_indicator_ranking("profit_loss", PERIOD)["indicator_rank"].is_monotonic_increasing
