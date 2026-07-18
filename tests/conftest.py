"""Shared real-data fixtures for engine regression tests."""

from pathlib import Path

import pytest

from data.excel_repository import ExcelBranchRepository

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def input_df():
    return ExcelBranchRepository(ROOT / "Data.xlsx").load_branch_data()
