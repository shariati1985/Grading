"""Future SQL Server scenario repository contract-compatible skeleton."""

from __future__ import annotations

from .models import ScenarioChangeRecord, ScenarioRecord, ScenarioResultSummary


class SqlServerScenarioRepository:
    """Placeholder for the production multi-user repository.

    The future implementation should use parameterized stored procedures or
    SQLAlchemy/pyodbc queries against ScenarioHeader, ScenarioChange,
    ScenarioResultSummary, and ScenarioAuditLog tables. Update/archive/delete
    contracts must include ``WHERE RowVersion = @ExpectedRowVersion`` and return
    the new version atomically. Read contracts must enforce owner/visibility,
    and list contracts must return headers only with server-side pagination.
    """

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string

    @staticmethod
    def _pending() -> None:
        raise NotImplementedError(
            "SQL Server scenario persistence is not implemented. Add pyodbc or "
            "SQLAlchemy and implement the documented normalized-table contracts."
        )

    def create_scenario(
        self,
        scenario: ScenarioRecord,
        changes: list[ScenarioChangeRecord],
        result_summaries: list[ScenarioResultSummary] | None = None,
    ) -> ScenarioRecord:
        self._pending()

    def update_scenario(
        self,
        scenario: ScenarioRecord,
        changes: list[ScenarioChangeRecord],
        expected_row_version: int,
        result_summaries: list[ScenarioResultSummary] | None = None,
    ) -> ScenarioRecord:
        self._pending()

    def get_scenario(
        self, scenario_id: str, requesting_user_id: str
    ) -> tuple[ScenarioRecord, list[ScenarioChangeRecord], list[ScenarioResultSummary]]:
        self._pending()

    def list_scenarios(
        self,
        requesting_user_id: str,
        include_shared: bool = True,
        status: str | None = None,
        *,
        search: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[ScenarioRecord]:
        self._pending()

    def delete_scenario(
        self, scenario_id: str, requesting_user_id: str, expected_row_version: int
    ) -> None:
        self._pending()

    def archive_scenario(
        self, scenario_id: str, requesting_user_id: str, expected_row_version: int
    ) -> ScenarioRecord:
        self._pending()

    def copy_scenario(
        self,
        source_scenario_id: str,
        new_owner_user_id: str,
        new_owner_display_name: str,
        new_name: str,
    ) -> ScenarioRecord:
        self._pending()
