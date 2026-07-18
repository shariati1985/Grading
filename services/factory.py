"""Local prototype service composition."""

from __future__ import annotations

from pathlib import Path

from persistence.sqlite_scenario_repository import SQLiteScenarioRepository

from .scenario_management_service import ScenarioManagementService
from .user_context import load_current_user


def create_local_scenario_service(project_root: str | Path) -> ScenarioManagementService:
    """Compose the local user and SQLite repository without global connections."""
    root = Path(project_root)
    user = load_current_user(root / "config" / "local_user.json")
    repository = SQLiteScenarioRepository(root / "storage" / "scenarios.db")
    return ScenarioManagementService(repository, user)
