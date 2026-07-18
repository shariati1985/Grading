"""Shared application-level data loading orchestration."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from data.excel_repository import ExcelBranchRepository
from engine.ranking_engine import ModelOutputs, run_ranking_model


def load_dashboard_data(
    file_path: str | Path, period: str | None = None
) -> tuple[pd.DataFrame, ModelOutputs]:
    """Load canonical branch data and calculate the baseline dashboard model."""
    data = ExcelBranchRepository(file_path).load_branch_data(period)
    return data, run_ranking_model(data)
