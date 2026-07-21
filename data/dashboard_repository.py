"""Dashboard repository adapter over authoritative ranking-engine outputs."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from data.dashboard_contracts import (
    BRANCH_INDICATOR_COLUMNS,
    BRANCH_SUMMARY_COLUMNS,
    INDICATOR_DEFINITION_COLUMNS,
    PERIOD_COLUMNS,
)
from engine.indicator_registry import INDICATOR_REGISTRY
from engine.ranking_engine import INDICATOR_KEYS, WEIGHTS, ModelOutputs


class DashboardDataValidationError(ValueError):
    """Raised when engine output cannot satisfy the dashboard contract."""


class DashboardRepository:
    """Expose canonical names without recalculating any domain value."""

    def __init__(
        self,
        outputs: ModelOutputs,
        period_id: str,
        *,
        period_label: str | None = None,
        calculation_timestamp: datetime | None = None,
    ) -> None:
        self._outputs = outputs
        self._period_id = str(period_id)
        self._period_label = period_label or self._period_id
        self._timestamp = calculation_timestamp or datetime.now(timezone.utc)

    def load_branch_summary(self) -> pd.DataFrame:
        source = self._outputs.final_result
        result = source.rename(
            columns={"region": "region_name", "rank": "final_rank"}
        ).copy()
        result["branch_code"] = result["branch_id"]
        result["region_id"] = result["region_name"]
        result["period_id"] = self._period_id
        result["period_label"] = self._period_label
        result["previous_rank"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
        result["rank_change"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
        result["calculation_timestamp"] = self._timestamp
        result = result.loc[:, BRANCH_SUMMARY_COLUMNS].reset_index(drop=True)
        self._validate_summary(result)
        return result

    def load_branch_indicators(self) -> pd.DataFrame:
        source = self._outputs.indicator_results
        result = source.rename(
            columns={
                "indicator_key": "indicator_id",
                "score": "normalized_score",
                "weighted_score": "weighted_contribution",
            }
        ).copy()
        result["branch_code"] = result["branch_id"]
        result["period_id"] = self._period_id
        result["indicator_name"] = result["indicator_id"].map(
            {key: definition.display_name for key, definition in INDICATOR_REGISTRY.items()}
        )
        result["weight"] = result["indicator_id"].map(WEIGHTS)
        result = result.loc[:, BRANCH_INDICATOR_COLUMNS].reset_index(drop=True)
        self._validate_indicators(result, source)
        return result

    def load_indicator_definitions(self) -> pd.DataFrame:
        rows = [
            {
                "indicator_id": key,
                "indicator_name": INDICATOR_REGISTRY[key].display_name,
                "weight": WEIGHTS[key],
                "direction": INDICATOR_REGISTRY[key].direction,
            }
            for key in INDICATOR_KEYS
        ]
        return pd.DataFrame(rows, columns=INDICATOR_DEFINITION_COLUMNS)

    def load_available_periods(self) -> pd.DataFrame:
        return pd.DataFrame(
            [(self._period_id, self._period_label)], columns=PERIOD_COLUMNS
        )

    @staticmethod
    def _validate_summary(frame: pd.DataFrame) -> None:
        if frame.duplicated(["branch_id", "period_id"]).any():
            raise DashboardDataValidationError("Duplicate branch-period summary records")

    @staticmethod
    def _validate_indicators(frame: pd.DataFrame, engine_source: pd.DataFrame) -> None:
        keys = ["branch_id", "period_id", "indicator_id"]
        if frame.duplicated(keys).any():
            raise DashboardDataValidationError("Duplicate branch-period-indicator records")
        if not frame["normalized_score"].between(1.0, 1000.0).all():
            raise DashboardDataValidationError("normalized_score must be between 1 and 1000")
        branch_counts = frame.groupby(["branch_id", "period_id"])["indicator_id"].nunique()
        if not branch_counts.eq(len(INDICATOR_KEYS)).all():
            raise DashboardDataValidationError("Each branch-period must have eight indicators")
        ranked_counts = frame.groupby(["period_id", "indicator_id"])["branch_id"].transform("size")
        if not frame["indicator_rank"].between(1, ranked_counts).all():
            raise DashboardDataValidationError("indicator_rank is outside the ranked population")
        expected_weights = frame["indicator_id"].map(WEIGHTS)
        if expected_weights.isna().any() or not np.allclose(frame["weight"], expected_weights):
            raise DashboardDataValidationError("Indicator weights do not match official weights")
        if not np.allclose(frame["weighted_contribution"], engine_source["weighted_score"]):
            raise DashboardDataValidationError(
                "weighted_contribution does not match the ranking-engine output"
            )
