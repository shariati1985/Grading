"""Tests for canonical Excel repository behavior."""

from pathlib import Path

import pandas as pd
import pytest

from data.contracts import CANONICAL_COLUMNS
from data.excel_repository import ExcelBranchRepository

ROOT = Path(__file__).resolve().parents[1]


def test_excel_repository_returns_canonical_schema_and_text_ids() -> None:
    data = ExcelBranchRepository(ROOT / "Data.xlsx").load_branch_data()
    assert tuple(data.columns) == CANONICAL_COLUMNS
    assert pd.api.types.is_object_dtype(data["branch_id"])
    assert data["branch_id"].map(type).eq(str).all()
    assert data["region"].ne("").any()


def test_duplicate_branch_id_raises(tmp_path: Path) -> None:
    source = pd.read_excel(ROOT / "Data.xlsx", dtype=object).head(2)
    source.iloc[1, 0] = source.iloc[0, 0]
    path = tmp_path / "duplicates.xlsx"
    source.to_excel(path, index=False)
    with pytest.raises(ValueError, match="Duplicate branch_id"):
        ExcelBranchRepository(path).load_branch_data()


def test_blank_branch_name_raises(tmp_path: Path) -> None:
    source = pd.read_excel(ROOT / "Data.xlsx", dtype=object).head(2)
    source.iloc[0, 1] = "  "
    path = tmp_path / "blank-name.xlsx"
    source.to_excel(path, index=False)
    with pytest.raises(ValueError, match="Blank branch_name"):
        ExcelBranchRepository(path).load_branch_data()


def test_leading_zero_branch_id_is_preserved(tmp_path: Path) -> None:
    source = pd.read_excel(ROOT / "Data.xlsx", dtype=object).head(1)
    source.iloc[0, 0] = "00101"
    path = tmp_path / "leading-zero.xlsx"
    source.to_excel(path, index=False)
    data = ExcelBranchRepository(path).load_branch_data()
    assert data.loc[0, "branch_id"] == "00101"
