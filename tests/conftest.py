"""Shared real-data fixtures for engine regression tests."""

from pathlib import Path

import pytest

from data.excel_repository import ExcelBranchRepository
from engine.indicator_registry import INDICATOR_REGISTRY
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def input_df():
    return ExcelBranchRepository(ROOT / "Data.xlsx").load_branch_data()


@pytest.fixture
def scenario_rule_baseline():
    values = {key: [100.0, 100.0] for key in INDICATOR_REGISTRY}
    return pd.DataFrame(
        {
            "branch_id": ["101", "202"],
            "branch_name": ["یک", "دو"],
            "region": ["الف", "ب"],
            **values,
        }
    )
