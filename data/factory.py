"""Runtime composition for branch-data repositories."""

from __future__ import annotations

from pathlib import Path

from config.runtime import RuntimeConfig
from data.excel_repository import ExcelBranchRepository
from data.sql_repository import SqlServerBranchRepository


def create_branch_repository(project_root: str | Path, config: RuntimeConfig):
    """Create the configured branch-data repository."""
    del project_root

    if config.data_source_type == "excel":
        return ExcelBranchRepository(config.data_file_path)

    if config.data_source_type == "sqlserver":
        if not config.data_source_connection_string:
            raise ValueError(
                "DATA_SOURCE_CONNECTION_STRING is required when DATA_SOURCE_TYPE=sqlserver"
            )
        return SqlServerBranchRepository(
            config.data_source_connection_string,
            config.data_source_table_or_view,
        )

    raise ValueError(
        f"Unsupported DATA_SOURCE_TYPE: {config.data_source_type!r}. "
        "Expected 'excel' or 'sqlserver'."
    )
