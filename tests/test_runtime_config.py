"""Tests for environment-backed deployment configuration."""

from __future__ import annotations

from config.runtime import load_runtime_config


def test_runtime_config_defaults_to_local_prototype(monkeypatch, tmp_path):
    for name in (
        "APP_ENV",
        "APP_VERSION",
        "BASE_PERIOD",
        "DATA_SOURCE_TYPE",
        "DATA_FILE_PATH",
        "DATA_SOURCE_CONNECTION_STRING",
        "DATA_SOURCE_TABLE_OR_VIEW",
        "SCENARIO_DB_TYPE",
        "SCENARIO_DB_PATH",
        "SCENARIO_DB_CONNECTION_STRING",
        "AUTH_MODE",
        "LOCAL_USER_CONFIG_PATH",
        "AUTH_ISSUER_URL",
        "AUTH_CLIENT_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    config = load_runtime_config(tmp_path)

    assert config.app_env == "local"
    assert config.base_period == "1404-04"
    assert config.data_source_type == "excel"
    assert config.data_file_path == tmp_path / "Data.xlsx"
    assert config.scenario_db_type == "sqlite"
    assert config.scenario_db_path == tmp_path / "storage/scenarios.db"
    assert config.auth_mode == "local"


def test_runtime_config_reads_production_integration_points(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BASE_PERIOD", "1405-01")
    monkeypatch.setenv("DATA_SOURCE_TYPE", "sqlserver")
    monkeypatch.setenv("DATA_SOURCE_CONNECTION_STRING", "driver=test")
    monkeypatch.setenv("DATA_SOURCE_TABLE_OR_VIEW", "dbo.vw_grading")
    monkeypatch.setenv("SCENARIO_DB_TYPE", "sqlserver")
    monkeypatch.setenv("SCENARIO_DB_CONNECTION_STRING", "driver=scenario")
    monkeypatch.setenv("AUTH_MODE", "enterprise")
    monkeypatch.setenv("AUTH_ISSUER_URL", "https://identity.bank.local")
    monkeypatch.setenv("AUTH_CLIENT_ID", "grading")

    config = load_runtime_config(tmp_path)

    assert config.is_production
    assert config.base_period == "1405-01"
    assert config.data_source_type == "sqlserver"
    assert config.data_source_connection_string == "driver=test"
    assert config.data_source_table_or_view == "dbo.vw_grading"
    assert config.scenario_db_type == "sqlserver"
    assert config.scenario_db_connection_string == "driver=scenario"
    assert config.auth_mode == "enterprise"
    assert config.auth_client_id == "grading"
