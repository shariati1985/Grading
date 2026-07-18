"""Repository contract and persistence-specific errors."""

from __future__ import annotations

from typing import Protocol

from .models import ScenarioChangeRecord, ScenarioRecord, ScenarioResultSummary


class ScenarioPersistenceError(RuntimeError):
    """Base class for scenario persistence failures."""


class ConcurrencyError(ScenarioPersistenceError):
    """Raised when an expected row version is stale."""


class AuthorizationError(ScenarioPersistenceError):
    """Raised when the requesting user lacks access or ownership."""


class NotFoundError(ScenarioPersistenceError):
    """Raised when a scenario identifier does not exist."""


class ScenarioRepository(Protocol):
    def create_scenario(
        self,
        scenario: ScenarioRecord,
        changes: list[ScenarioChangeRecord],
        result_summaries: list[ScenarioResultSummary] | None = None,
    ) -> ScenarioRecord: ...

    def update_scenario(
        self,
        scenario: ScenarioRecord,
        changes: list[ScenarioChangeRecord],
        expected_row_version: int,
        result_summaries: list[ScenarioResultSummary] | None = None,
        *,
        requesting_user_id: str,
    ) -> ScenarioRecord: ...

    def get_scenario(
        self, scenario_id: str, requesting_user_id: str
    ) -> tuple[ScenarioRecord, list[ScenarioChangeRecord], list[ScenarioResultSummary]]: ...

    def list_scenarios(
        self,
        requesting_user_id: str,
        status: str | None = None,
        *,
        search: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[ScenarioRecord]: ...

    def delete_scenario(
        self, scenario_id: str, requesting_user_id: str, expected_row_version: int
    ) -> None: ...

    def archive_scenario(
        self, scenario_id: str, requesting_user_id: str, expected_row_version: int
    ) -> ScenarioRecord: ...

    def copy_scenario(
        self,
        source_scenario_id: str,
        new_owner_user_id: str,
        new_owner_display_name: str,
        new_name: str,
    ) -> ScenarioRecord: ...
