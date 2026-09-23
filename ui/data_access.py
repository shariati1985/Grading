"""Shared application-level data loading orchestration."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.runtime import RuntimeConfig
from data.excel_repository import ExcelBranchRepository
from data.factory import create_branch_repository
from engine.ranking_engine import ModelOutputs, run_ranking_model


def load_dashboard_data(
    file_path: str | Path, period: str | None = None
) -> tuple[pd.DataFrame, ModelOutputs]:
    """Backward-compatible Excel loader for tests and local prototype use."""
    data = ExcelBranchRepository(file_path).load_branch_data(period)
    return data, run_ranking_model(data)


def load_configured_dashboard_data(
    project_root: str | Path,
    config: RuntimeConfig,
) -> tuple[pd.DataFrame, ModelOutputs]:
    """Load canonical branch data from the configured runtime repository."""
    repository = create_branch_repository(project_root, config)
    data = repository.load_branch_data(config.base_period)
    return data, run_ranking_model(data)
