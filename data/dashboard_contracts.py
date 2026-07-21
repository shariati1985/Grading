"""Canonical, calculation-free data contracts for dashboard consumers."""

from __future__ import annotations

from typing import Final, Protocol

import pandas as pd

BRANCH_SUMMARY_COLUMNS: Final[tuple[str, ...]] = (
    "branch_id", "branch_code", "branch_name", "region_id", "region_name",
    "period_id", "period_label", "final_score", "final_rank", "grade",
    "previous_rank", "rank_change", "calculation_timestamp",
)

BRANCH_INDICATOR_COLUMNS: Final[tuple[str, ...]] = (
    "branch_id", "branch_code", "period_id", "indicator_id", "indicator_name",
    "raw_value", "shifted_value", "log_value", "normalized_score",
    "indicator_rank", "weight", "weighted_contribution",
)

INDICATOR_DEFINITION_COLUMNS: Final[tuple[str, ...]] = (
    "indicator_id", "indicator_name", "weight", "direction",
)

PERIOD_COLUMNS: Final[tuple[str, ...]] = ("period_id", "period_label")


class DashboardRepositoryProtocol(Protocol):
    """Read-only access to ranking-engine output shaped for dashboards."""

    def load_branch_summary(self) -> pd.DataFrame: ...
    def load_branch_indicators(self) -> pd.DataFrame: ...
    def load_indicator_definitions(self) -> pd.DataFrame: ...
    def load_available_periods(self) -> pd.DataFrame: ...
