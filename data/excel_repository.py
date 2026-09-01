"""Excel-backed branch data repository."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Final

import pandas as pd

from .contracts import CANONICAL_COLUMNS

COLUMN_MAPPING: Final[dict[str, str]] = {
    "کد شعبه": "branch_id",
    "نام شعبه": "branch_name",
    "منطقه": "region",
    "میانگین سپرده ها": "avg_deposits",
    "تعداد سپرده ها": "deposit_count",
    "میانگین تسهیلات": "avg_loans",
    "تعداد تسهیلات": "loan_count",
    "میانگین تعهدات": "avg_commitments",
    "تعداد تعهدات": "commitment_count",
    "حجم عملیات": "transaction_volume",
    "سود (زیان)": "profit_loss",
}
NON_BRANCH_NAMES: Final[frozenset[str]] = frozenset({"اوزان", "وزن", "weight", "weights"})
INDICATOR_COLUMNS: Final[tuple[str, ...]] = CANONICAL_COLUMNS[3:]
PERSIAN_DIGITS: Final[str] = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS: Final[str] = "٠١٢٣٤٥٦٧٨٩"
ENGLISH_DIGITS: Final[str] = "0123456789"
DIGIT_TRANSLATION: Final[dict[int, str]] = str.maketrans(
    PERSIAN_DIGITS + ARABIC_DIGITS, ENGLISH_DIGITS + ENGLISH_DIGITS
)


def normalize_text(value: object) -> str:
    """Normalize Persian/Arabic character variants and whitespace."""
    text = "" if pd.isna(value) else str(value)
    text = text.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
    text = text.replace("\u200c", " ")
    return re.sub(r"\s+", " ", text, flags=re.UNICODE).strip()


def clean_numeric_value(value: object) -> str:
    """Return a locale-normalized numeric string."""
    if pd.isna(value):
        return ""
    text = str(value).translate(DIGIT_TRANSLATION).strip()
    text = text.replace(",", "").replace("،", "").replace("٬", "")
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = re.sub(r"[^\d.\-+]", "", text)
    if text.count(".") > 1:
        first, *rest = text.split(".")
        text = first + "." + "".join(rest)
    return text


def normalize_branch_id(value: object) -> str:
    """Normalize an identifier as text without inventing or dropping zeros."""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return normalize_text(value).translate(DIGIT_TRANSLATION)


class ExcelBranchRepository:
    """Load and validate canonical branch data from an Excel workbook."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)

    def load_branch_data(self, period: str | None = None) -> pd.DataFrame:
        """Read the workbook without modifying it; ``period`` is reserved."""
        del period
        if not self.file_path.exists():
            raise FileNotFoundError(f"Branch data workbook not found: {self.file_path}")

        source = pd.read_excel(self.file_path, dtype=object)
        headers = [normalize_text(column) for column in source.columns]
        duplicate_headers = sorted({name for name in headers if headers.count(name) > 1})
        if duplicate_headers:
            raise ValueError(
                "Duplicate columns after normalization: " + ", ".join(duplicate_headers)
            )
        source.columns = headers
        normalized_mapping = {
            normalize_text(source_name): canonical_name
            for source_name, canonical_name in COLUMN_MAPPING.items()
        }
        source = source.rename(columns=normalized_mapping)
        missing = [column for column in CANONICAL_COLUMNS if column not in source.columns]
        if missing:
            raise ValueError("Missing required branch data columns: " + ", ".join(missing))

        data = source.loc[:, CANONICAL_COLUMNS].copy()
        data["branch_name"] = data["branch_name"].map(normalize_text)
        non_branch = data["branch_name"].str.lower().isin(NON_BRANCH_NAMES)
        data = data.loc[~non_branch].copy().reset_index(drop=True)

        if data["branch_name"].eq("").any():
            rows = (data.index[data["branch_name"].eq("")] + 2).tolist()
            raise ValueError(f"Blank branch_name values found at Excel rows: {rows}")

        # Keep identifiers on the long-standing object/string contract across
        # pandas versions (pandas 3 otherwise infers its new StringDtype).
        data["branch_id"] = data["branch_id"].map(normalize_branch_id).astype(object)
        if data["branch_id"].eq("").any():
            raise ValueError("Blank branch_id values are not allowed")
        duplicate_ids = data.loc[
            data["branch_id"].duplicated(keep=False), "branch_id"
        ].unique()
        if len(duplicate_ids):
            raise ValueError(
                "Duplicate branch_id values: " + ", ".join(map(str, duplicate_ids))
            )

        data["region"] = data["region"].map(normalize_text)
        for column in INDICATOR_COLUMNS:
            cleaned = data[column].map(clean_numeric_value)
            data[column] = pd.to_numeric(cleaned, errors="coerce").fillna(0.0).astype(float)
        return data.loc[:, CANONICAL_COLUMNS]
