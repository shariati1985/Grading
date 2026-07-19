"""Query service for canonical dashboard datasets; no domain calculations."""

from __future__ import annotations

import pandas as pd

from data.dashboard_contracts import DashboardRepositoryProtocol


class DashboardService:
    def __init__(self, repository: DashboardRepositoryProtocol) -> None:
        self._repository = repository

    def get_branch_summary(self, branch_id: str, period_id: str) -> pd.DataFrame:
        frame = self._repository.load_branch_summary()
        return frame.loc[
            frame["branch_id"].astype(str).eq(str(branch_id))
            & frame["period_id"].astype(str).eq(str(period_id))
        ].reset_index(drop=True)

    def get_branch_indicators(self, branch_id: str, period_id: str) -> pd.DataFrame:
        frame = self._repository.load_branch_indicators()
        return frame.loc[
            frame["branch_id"].astype(str).eq(str(branch_id))
            & frame["period_id"].astype(str).eq(str(period_id))
        ].reset_index(drop=True)

    def get_branch_indicator(
        self, branch_id: str, indicator_id: str, period_id: str
    ) -> pd.DataFrame:
        frame = self.get_branch_indicators(branch_id, period_id)
        return frame.loc[frame["indicator_id"].eq(indicator_id)].reset_index(drop=True)

    def get_branch_ranking(self, period_id: str) -> pd.DataFrame:
        frame = self._repository.load_branch_summary()
        return frame.loc[frame["period_id"].astype(str).eq(str(period_id))].sort_values(
            "final_rank"
        ).reset_index(drop=True)

    def get_indicator_ranking(self, indicator_id: str, period_id: str) -> pd.DataFrame:
        frame = self._repository.load_branch_indicators()
        return frame.loc[
            frame["indicator_id"].eq(indicator_id)
            & frame["period_id"].astype(str).eq(str(period_id))
        ].sort_values("indicator_rank").reset_index(drop=True)
