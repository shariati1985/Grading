"""SQLite schema migrations for scenario persistence."""

from __future__ import annotations

import sqlite3


def migrate_sqlite(connection: sqlite3.Connection) -> None:
    """Create the normalized scenario tables and indexes idempotently."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS scenario_header (
            scenario_id TEXT PRIMARY KEY,
            scenario_name TEXT NOT NULL,
            baseline_period TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            owner_display_name TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('draft', 'executed', 'archived')),
            visibility TEXT NOT NULL CHECK (visibility IN ('private', 'shared')),
            model_version TEXT NOT NULL,
            weights_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            row_version INTEGER NOT NULL CHECK (row_version >= 1),
            selected_branch_ids_json TEXT NOT NULL,
            summary_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scenario_change (
            scenario_id TEXT NOT NULL,
            branch_id TEXT NOT NULL,
            branch_name TEXT NOT NULL,
            indicator_key TEXT NOT NULL,
            baseline_value REAL NOT NULL,
            scenario_value REAL NOT NULL,
            absolute_change REAL NOT NULL,
            percentage_change REAL,
            edit_mode TEXT NOT NULL DEFAULT 'direct' CHECK (edit_mode IN ('percent', 'direct')),
            PRIMARY KEY (scenario_id, branch_id, indicator_key),
            FOREIGN KEY (scenario_id) REFERENCES scenario_header(scenario_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS scenario_result_summary (
            scenario_id TEXT NOT NULL,
            branch_id TEXT NOT NULL,
            baseline_score REAL NOT NULL,
            scenario_score REAL NOT NULL,
            baseline_rank INTEGER NOT NULL,
            scenario_rank INTEGER NOT NULL,
            baseline_grade TEXT NOT NULL,
            scenario_grade TEXT NOT NULL,
            rank_change INTEGER NOT NULL,
            score_change REAL NOT NULL,
            PRIMARY KEY (scenario_id, branch_id),
            FOREIGN KEY (scenario_id) REFERENCES scenario_header(scenario_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS scenario_audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_id TEXT NOT NULL,
            action TEXT NOT NULL CHECK (action IN ('create','update','execute','archive','delete','copy')),
            user_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            old_row_version INTEGER,
            new_row_version INTEGER,
            details_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS ix_scenario_header_owner ON scenario_header(owner_user_id);
        CREATE INDEX IF NOT EXISTS ix_scenario_header_visibility ON scenario_header(visibility);
        CREATE INDEX IF NOT EXISTS ix_scenario_header_status ON scenario_header(status);
        CREATE INDEX IF NOT EXISTS ix_scenario_header_created ON scenario_header(created_at DESC);
        CREATE INDEX IF NOT EXISTS ix_scenario_change_scenario ON scenario_change(scenario_id);
        CREATE INDEX IF NOT EXISTS ix_scenario_result_scenario ON scenario_result_summary(scenario_id);
        CREATE INDEX IF NOT EXISTS ix_scenario_audit_scenario ON scenario_audit_log(scenario_id);
        """
    )
    change_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(scenario_change)").fetchall()
    }
    if "edit_mode" not in change_columns:
        connection.execute(
            "ALTER TABLE scenario_change ADD COLUMN edit_mode TEXT NOT NULL DEFAULT 'direct'"
        )
