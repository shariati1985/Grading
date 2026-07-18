"""Scenario persistence abstractions and implementations."""

from .contracts import (
    AuthorizationError,
    ConcurrencyError,
    NotFoundError,
    ScenarioRepository,
)
from .models import ScenarioChangeRecord, ScenarioRecord, ScenarioResultSummary
from .sqlite_scenario_repository import SQLiteScenarioRepository
from .sqlserver_scenario_repository import SqlServerScenarioRepository

__all__ = [
    "AuthorizationError",
    "ConcurrencyError",
    "NotFoundError",
    "ScenarioRepository",
    "ScenarioChangeRecord",
    "ScenarioRecord",
    "ScenarioResultSummary",
    "SQLiteScenarioRepository",
    "SqlServerScenarioRepository",
]
