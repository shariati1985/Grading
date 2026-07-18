"""Future SQL Server implementation of the branch repository contract."""

from __future__ import annotations

import pandas as pd


class SqlServerBranchRepository:
    """SQL Server repository placeholder.

    A future query (via pyodbc or SQLAlchemy) must return: branch_id,
    branch_name, region, avg_deposits, deposit_count, avg_loans, loan_count,
    avg_commitments, commitment_count, transaction_volume, and profit_loss.
    """

    def __init__(self, connection_string: str, table_or_view_name: str) -> None:
        self.connection_string = connection_string
        self.table_or_view_name = table_or_view_name

    def load_branch_data(self, period: str | None = None) -> pd.DataFrame:
        """Raise until a SQL Server driver and query strategy are selected."""
        del period
        raise NotImplementedError(
            "SQL Server branch loading is not implemented yet; add a pyodbc or "
            "SQLAlchemy implementation that returns the canonical branch schema."
        )
