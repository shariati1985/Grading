"""Scenario-service composition for local and production deployment."""

from __future__ import annotations

from pathlib import Path

from config.runtime import RuntimeConfig
from persistence.sqlite_scenario_repository import SQLiteScenarioRepository
from persistence.sqlserver_scenario_repository import SqlServerScenarioRepository

from .scenario_management_service import ScenarioManagementService
from .user_context import load_current_user


def _resolve_user(project_root: Path, config: RuntimeConfig):
    if config.auth_mode == "local":
        return load_current_user(config.local_user_config_path)

    if config.auth_mode == "enterprise":
        raise NotImplementedError(
            "Enterprise authentication adapter is not implemented. "
            "Bank IT must map the authenticated enterprise identity to CurrentUser."
        )

    raise ValueError(
        f"Unsupported AUTH_MODE: {config.auth_mode!r}. "
        "Expected 'local' or 'enterprise'."
    )


def create_scenario_service(
    project_root: str | Path, config: RuntimeConfig
) -> ScenarioManagementService:
    """Compose the scenario service from runtime configuration."""
    root = Path(project_root)
    user = _resolve_user(root, config)

    if config.scenario_db_type == "sqlite":
        repository = SQLiteScenarioRepository(config.scenario_db_path)
    elif config.scenario_db_type == "sqlserver":
        if not config.scenario_db_connection_string:
            raise ValueError(
                "SCENARIO_DB_CONNECTION_STRING is required when SCENARIO_DB_TYPE=sqlserver"
            )
        repository = SqlServerScenarioRepository(
            config.scenario_db_connection_string
        )
    else:
        raise ValueError(
            f"Unsupported SCENARIO_DB_TYPE: {config.scenario_db_type!r}. "
            "Expected 'sqlite' or 'sqlserver'."
        )

    return ScenarioManagementService(repository, user)


def create_local_scenario_service(project_root: str | Path) -> ScenarioManagementService:
    """Backward-compatible local prototype composition."""
    root = Path(project_root)
    from config.runtime import load_runtime_config

    config = load_runtime_config(root)
    if config.auth_mode != "local" or config.scenario_db_type != "sqlite":
        raise ValueError(
            "create_local_scenario_service requires AUTH_MODE=local and "
            "SCENARIO_DB_TYPE=sqlite"
        )
    return create_scenario_service(root, config)
