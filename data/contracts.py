"""Contracts and schema constants for branch data sources."""

from __future__ import annotations

from typing import Final, Protocol

import pandas as pd

CANONICAL_COLUMNS: Final[tuple[str, ...]] = (
    "branch_id",
    "branch_name",
    "region",
    "avg_deposits",
    "deposit_count",
    "avg_loans",
    "loan_count",
    "avg_commitments",
    "commitment_count",
    "transaction_volume",
    "profit_loss",
)


class BranchDataRepository(Protocol):
    """Data-source-independent access to canonical branch data."""

    def load_branch_data(self, period: str | None = None) -> pd.DataFrame:
        """Return branch data in :data:`CANONICAL_COLUMNS` order."""
        ...
