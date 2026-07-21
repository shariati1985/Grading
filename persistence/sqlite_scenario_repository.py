"""Transactional SQLite scenario repository for the local prototype."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from typing import Any, Iterator
from uuid import UUID, uuid4

from .contracts import AuthorizationError, ConcurrencyError, NotFoundError
from .migrations import migrate_sqlite
from .models import ScenarioChangeRecord, ScenarioRecord, ScenarioResultSummary

ALLOWED_STATUSES = frozenset({"draft", "executed", "archived"})
ALLOWED_VISIBILITIES = frozenset({"private", "shared"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class SQLiteScenarioRepository:
    """Persist scenario headers and compact details in a local SQLite database.

    Connections are opened per operation, transactions remain short, and WAL
    mode plus a busy timeout improve local concurrent-reader behavior. SQL
    Server remains the required production backend for approximately 600 users.
    """

    def __init__(self, database_path: str | Path = "storage/scenarios.db") -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            migrate_sqlite(connection)
            connection.commit()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _validate_record(scenario: ScenarioRecord) -> None:
        try:
            UUID(scenario.scenario_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("scenario_id must be a UUID string") from exc
        if scenario.status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported scenario status: {scenario.status}")
        if scenario.visibility not in ALLOWED_VISIBILITIES:
            raise ValueError(f"Unsupported scenario visibility: {scenario.visibility}")

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> ScenarioRecord:
        return ScenarioRecord(
            scenario_id=row["scenario_id"],
            scenario_name=row["scenario_name"],
            baseline_period=row["baseline_period"],
            owner_user_id=row["owner_user_id"],
            owner_display_name=row["owner_display_name"],
            status=row["status"],
            visibility=row["visibility"],
            model_version=row["model_version"],
            weights_version=row["weights_version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            row_version=int(row["row_version"]),
            selected_branch_ids=list(json.loads(row["selected_branch_ids_json"])),
            summary=dict(json.loads(row["summary_json"])),
        )

    @staticmethod
    def _insert_header(connection: sqlite3.Connection, scenario: ScenarioRecord) -> None:
        connection.execute(
            """
            INSERT INTO scenario_header (
                scenario_id, scenario_name, baseline_period, owner_user_id,
                owner_display_name, status, visibility, model_version,
                weights_version, created_at, updated_at, row_version,
                selected_branch_ids_json, summary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario.scenario_id,
                scenario.scenario_name,
                scenario.baseline_period,
                scenario.owner_user_id,
                scenario.owner_display_name,
                scenario.status,
                scenario.visibility,
                scenario.model_version,
                scenario.weights_version,
                _timestamp(scenario.created_at),
                _timestamp(scenario.updated_at),
                scenario.row_version,
                _json(scenario.selected_branch_ids),
                _json(scenario.summary),
            ),
        )

    @staticmethod
    def _insert_changes(
        connection: sqlite3.Connection,
        scenario_id: str,
        changes: list[ScenarioChangeRecord],
    ) -> None:
        connection.executemany(
            """
            INSERT INTO scenario_change (
                scenario_id, branch_id, branch_name, indicator_key,
                baseline_value, scenario_value, absolute_change, percentage_change, edit_mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scenario_id,
                    item.branch_id,
                    item.branch_name,
                    item.indicator_key,
                    item.baseline_value,
                    item.scenario_value,
                    item.absolute_change,
                    None if not math.isfinite(item.percentage_change) else item.percentage_change,
                    item.edit_mode,
                )
                for item in changes
            ],
        )

    @staticmethod
    def _insert_results(
        connection: sqlite3.Connection,
        scenario_id: str,
        results: list[ScenarioResultSummary],
    ) -> None:
        connection.executemany(
            """
            INSERT INTO scenario_result_summary (
                scenario_id, branch_id, baseline_score, scenario_score,
                baseline_rank, scenario_rank, baseline_grade, scenario_grade,
                rank_change, score_change
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scenario_id,
                    item.branch_id,
                    item.baseline_score,
                    item.scenario_score,
                    item.baseline_rank,
                    item.scenario_rank,
                    item.baseline_grade,
                    item.scenario_grade,
                    item.rank_change,
                    item.score_change,
                )
                for item in results
            ],
        )

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        scenario_id: str,
        action: str,
        user_id: str,
        old_version: int | None,
        new_version: int | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO scenario_audit_log (
                scenario_id, action, user_id, timestamp,
                old_row_version, new_row_version, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_id,
                action,
                user_id,
                _timestamp(_utc_now()),
                old_version,
                new_version,
                _json(details or {}),
            ),
        )

    @staticmethod
    def _header_or_error(connection: sqlite3.Connection, scenario_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM scenario_header WHERE scenario_id = ?", (scenario_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Scenario not found: {scenario_id}")
        return row

    @classmethod
    def _owned_header(
        cls, connection: sqlite3.Connection, scenario_id: str, user_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM scenario_header WHERE scenario_id = ? AND owner_user_id = ?",
            (scenario_id, user_id),
        ).fetchone()
        if row is not None:
            return row
        cls._header_or_error(connection, scenario_id)
        raise AuthorizationError("Only the scenario owner may access this scenario")

    def create_scenario(
        self,
        scenario: ScenarioRecord,
        changes: list[ScenarioChangeRecord],
        result_summaries: list[ScenarioResultSummary] | None = None,
    ) -> ScenarioRecord:
        self._validate_record(scenario)
        now = _utc_now()
        created = replace(
            scenario, visibility="private", created_at=now, updated_at=now, row_version=1
        )
        with self._transaction() as connection:
            self._insert_header(connection, created)
            self._insert_changes(connection, created.scenario_id, changes)
            self._insert_results(connection, created.scenario_id, result_summaries or [])
            self._audit(
                connection,
                created.scenario_id,
                "create",
                created.owner_user_id,
                None,
                1,
                {"status": created.status, "visibility": created.visibility},
            )
            if created.status == "executed":
                self._audit(
                    connection,
                    created.scenario_id,
                    "execute",
                    created.owner_user_id,
                    1,
                    1,
                    {"result_summary_count": len(result_summaries or [])},
                )
        return created

    def update_scenario(
        self,
        scenario: ScenarioRecord,
        changes: list[ScenarioChangeRecord],
        expected_row_version: int,
        result_summaries: list[ScenarioResultSummary] | None = None,
        *,
        requesting_user_id: str,
    ) -> ScenarioRecord:
        self._validate_record(scenario)
        with self._transaction() as connection:
            current = self._owned_header(
                connection, scenario.scenario_id, requesting_user_id
            )
            actual_version = int(current["row_version"])
            if actual_version != expected_row_version:
                raise ConcurrencyError(
                    f"Scenario was changed by another session; expected row_version "
                    f"{expected_row_version}, current is {actual_version}"
                )
            updated = replace(
                scenario,
                owner_user_id=current["owner_user_id"],
                owner_display_name=current["owner_display_name"],
                visibility="private",
                created_at=datetime.fromisoformat(current["created_at"]),
                updated_at=_utc_now(),
                row_version=actual_version + 1,
            )
            cursor = connection.execute(
                """
                UPDATE scenario_header SET
                    scenario_name = ?, baseline_period = ?, status = ?, visibility = ?,
                    model_version = ?, weights_version = ?, updated_at = ?, row_version = ?,
                    selected_branch_ids_json = ?, summary_json = ?
                WHERE scenario_id = ? AND owner_user_id = ? AND row_version = ?
                """,
                (
                    updated.scenario_name,
                    updated.baseline_period,
                    updated.status,
                    updated.visibility,
                    updated.model_version,
                    updated.weights_version,
                    _timestamp(updated.updated_at),
                    updated.row_version,
                    _json(updated.selected_branch_ids),
                    _json(updated.summary),
                    updated.scenario_id,
                    requesting_user_id,
                    expected_row_version,
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrencyError("Scenario changed during update")
            connection.execute(
                "DELETE FROM scenario_change WHERE scenario_id = ?", (updated.scenario_id,)
            )
            connection.execute(
                "DELETE FROM scenario_result_summary WHERE scenario_id = ?",
                (updated.scenario_id,),
            )
            self._insert_changes(connection, updated.scenario_id, changes)
            self._insert_results(connection, updated.scenario_id, result_summaries or [])
            self._audit(
                connection,
                updated.scenario_id,
                "update",
                updated.owner_user_id,
                actual_version,
                updated.row_version,
                {"status": updated.status, "visibility": updated.visibility},
            )
            if updated.status == "executed":
                self._audit(
                    connection,
                    updated.scenario_id,
                    "execute",
                    updated.owner_user_id,
                    actual_version,
                    updated.row_version,
                    {"result_summary_count": len(result_summaries or [])},
                )
        return updated

    def get_scenario(
        self, scenario_id: str, requesting_user_id: str
    ) -> tuple[ScenarioRecord, list[ScenarioChangeRecord], list[ScenarioResultSummary]]:
        with self._connection() as connection:
            row = self._owned_header(connection, scenario_id, requesting_user_id)
            change_rows = connection.execute(
                "SELECT * FROM scenario_change WHERE scenario_id = ? ORDER BY branch_id, indicator_key",
                (scenario_id,),
            ).fetchall()
            result_rows = connection.execute(
                "SELECT * FROM scenario_result_summary WHERE scenario_id = ? ORDER BY branch_id",
                (scenario_id,),
            ).fetchall()
        changes = [
            ScenarioChangeRecord(
                scenario_id=item["scenario_id"],
                branch_id=item["branch_id"],
                branch_name=item["branch_name"],
                indicator_key=item["indicator_key"],
                baseline_value=float(item["baseline_value"]),
                scenario_value=float(item["scenario_value"]),
                absolute_change=float(item["absolute_change"]),
                percentage_change=(
                    math.nan if item["percentage_change"] is None else float(item["percentage_change"])
                ),
                edit_mode=item["edit_mode"],
            )
            for item in change_rows
        ]
        results = [
            ScenarioResultSummary(
                scenario_id=item["scenario_id"],
                branch_id=item["branch_id"],
                baseline_score=float(item["baseline_score"]),
                scenario_score=float(item["scenario_score"]),
                baseline_rank=int(item["baseline_rank"]),
                scenario_rank=int(item["scenario_rank"]),
                baseline_grade=item["baseline_grade"],
                scenario_grade=item["scenario_grade"],
                rank_change=int(item["rank_change"]),
                score_change=float(item["score_change"]),
            )
            for item in result_rows
        ]
        return self._record_from_row(row), changes, results

    def list_scenarios(
        self,
        requesting_user_id: str,
        status: str | None = None,
        *,
        search: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[ScenarioRecord]:
        if status is not None and status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported scenario status: {status}")
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        clauses = ["owner_user_id = ?"]
        parameters: list[Any] = [requesting_user_id]
        if status is not None:
            clauses.append("status = ?")
            parameters.append(status)
        if search and search.strip():
            clauses.append("scenario_name LIKE ? ESCAPE '\\'")
            escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            parameters.append(f"%{escaped}%")
        parameters.extend([limit, offset])
        sql = (
            "SELECT * FROM scenario_header WHERE "
            + " AND ".join(clauses)
            + " ORDER BY updated_at DESC, scenario_id LIMIT ? OFFSET ?"
        )
        with self._connection() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [self._record_from_row(row) for row in rows]

    def delete_scenario(
        self, scenario_id: str, requesting_user_id: str, expected_row_version: int
    ) -> None:
        with self._transaction() as connection:
            row = self._owned_header(connection, scenario_id, requesting_user_id)
            actual_version = int(row["row_version"])
            if actual_version != expected_row_version:
                raise ConcurrencyError("Scenario was changed before deletion")
            self._audit(
                connection,
                scenario_id,
                "delete",
                requesting_user_id,
                actual_version,
                None,
                {"scenario_name": row["scenario_name"]},
            )
            cursor = connection.execute(
                """DELETE FROM scenario_header
                   WHERE scenario_id = ? AND owner_user_id = ? AND row_version = ?""",
                (scenario_id, requesting_user_id, expected_row_version),
            )
            if cursor.rowcount != 1:
                raise ConcurrencyError("Scenario changed during deletion")

    def archive_scenario(
        self, scenario_id: str, requesting_user_id: str, expected_row_version: int
    ) -> ScenarioRecord:
        with self._transaction() as connection:
            row = self._owned_header(connection, scenario_id, requesting_user_id)
            actual_version = int(row["row_version"])
            if actual_version != expected_row_version:
                raise ConcurrencyError("Scenario was changed before archiving")
            new_version = actual_version + 1
            updated_at = _utc_now()
            cursor = connection.execute(
                """UPDATE scenario_header SET status = 'archived', updated_at = ?, row_version = ?
                   WHERE scenario_id = ? AND owner_user_id = ? AND row_version = ?""",
                (
                    _timestamp(updated_at),
                    new_version,
                    scenario_id,
                    requesting_user_id,
                    expected_row_version,
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrencyError("Scenario changed during archive")
            self._audit(
                connection,
                scenario_id,
                "archive",
                requesting_user_id,
                actual_version,
                new_version,
            )
            updated_row = connection.execute(
                "SELECT * FROM scenario_header WHERE scenario_id = ?", (scenario_id,)
            ).fetchone()
        assert updated_row is not None
        return self._record_from_row(updated_row)

    def copy_scenario(
        self,
        source_scenario_id: str,
        new_owner_user_id: str,
        new_owner_display_name: str,
        new_name: str,
    ) -> ScenarioRecord:
        if not new_name.strip():
            raise ValueError("new_name cannot be blank")
        with self._transaction() as connection:
            source_row = self._owned_header(
                connection, source_scenario_id, new_owner_user_id
            )
            source = self._record_from_row(source_row)
            now = _utc_now()
            copied = replace(
                source,
                scenario_id=str(uuid4()),
                scenario_name=new_name.strip(),
                owner_user_id=new_owner_user_id,
                owner_display_name=new_owner_display_name,
                visibility="private",
                created_at=now,
                updated_at=now,
                row_version=1,
            )
            self._insert_header(connection, copied)
            connection.execute(
                """
                INSERT INTO scenario_change (
                    scenario_id, branch_id, branch_name, indicator_key,
                    baseline_value, scenario_value, absolute_change, percentage_change, edit_mode
                )
                SELECT ?, branch_id, branch_name, indicator_key,
                    baseline_value, scenario_value, absolute_change, percentage_change, edit_mode
                FROM scenario_change WHERE scenario_id = ?
                """,
                (copied.scenario_id, source_scenario_id),
            )
            connection.execute(
                """
                INSERT INTO scenario_result_summary (
                    scenario_id, branch_id, baseline_score, scenario_score,
                    baseline_rank, scenario_rank, baseline_grade, scenario_grade,
                    rank_change, score_change
                )
                SELECT ?, branch_id, baseline_score, scenario_score,
                    baseline_rank, scenario_rank, baseline_grade, scenario_grade,
                    rank_change, score_change
                FROM scenario_result_summary WHERE scenario_id = ?
                """,
                (copied.scenario_id, source_scenario_id),
            )
            self._audit(
                connection,
                copied.scenario_id,
                "copy",
                new_owner_user_id,
                None,
                1,
                {"source_scenario_id": source_scenario_id},
            )
        return copied
