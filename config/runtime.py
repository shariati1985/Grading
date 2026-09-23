"""Environment-backed runtime configuration.

No secrets are read from source-controlled files. Production values are expected
to be injected by the bank's approved deployment / secret-management mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class RuntimeConfig:
    app_env: str
    app_version: str
    base_period: str

    data_source_type: str
    data_file_path: Path
    data_source_connection_string: str
    data_source_table_or_view: str

    scenario_db_type: str
    scenario_db_path: Path
    scenario_db_connection_string: str

    auth_mode: str
    local_user_config_path: Path
    auth_issuer_url: str
    auth_client_id: str

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


def _text(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def load_runtime_config(project_root: str | Path) -> RuntimeConfig:
    """Load deployment configuration from environment variables."""
    root = Path(project_root)

    return RuntimeConfig(
        app_env=_text("APP_ENV", "local"),
        app_version=_text("APP_VERSION", "1.0.0"),
        base_period=_text("BASE_PERIOD", "1404-04"),
        data_source_type=_text("DATA_SOURCE_TYPE", "excel").lower(),
        data_file_path=root / _text("DATA_FILE_PATH", "Data.xlsx"),
        data_source_connection_string=_text("DATA_SOURCE_CONNECTION_STRING"),
        data_source_table_or_view=_text("DATA_SOURCE_TABLE_OR_VIEW", "vw_BranchGradingInput"),
        scenario_db_type=_text("SCENARIO_DB_TYPE", "sqlite").lower(),
        scenario_db_path=root / _text("SCENARIO_DB_PATH", "storage/scenarios.db"),
        scenario_db_connection_string=_text("SCENARIO_DB_CONNECTION_STRING"),
        auth_mode=_text("AUTH_MODE", "local").lower(),
        local_user_config_path=root / _text(
            "LOCAL_USER_CONFIG_PATH", "config/local_user.json"
        ),
        auth_issuer_url=_text("AUTH_ISSUER_URL"),
        auth_client_id=_text("AUTH_CLIENT_ID"),
    )
