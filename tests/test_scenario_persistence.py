"""SQLite persistence, access, concurrency, and audit tests."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import json
import inspect
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest

from persistence import (
    AuthorizationError,
    ConcurrencyError,
    NotFoundError,
    SQLiteScenarioRepository,
)
from persistence.models import ScenarioChangeRecord, ScenarioRecord, ScenarioResultSummary
from persistence.contracts import ScenarioRepository
from persistence.sqlserver_scenario_repository import SqlServerScenarioRepository
from services.user_context import load_current_user


def scenario_record(
    *, visibility: str = "private", status: str = "draft", owner: str = "user.one"
) -> ScenarioRecord:
    now = datetime.now(timezone.utc)
    return ScenarioRecord(
        scenario_id=str(uuid4()),
        scenario_name="سناریوی آزمون",
        baseline_period="1404-04",
        owner_user_id=owner,
        owner_display_name="کاربر یک",
        status=status,
        visibility=visibility,
        model_version="1.0",
        weights_version="1.0",
        created_at=now,
        updated_at=now,
        row_version=1,
        selected_branch_ids=["101"],
        summary={"changed_branch_count": 1},
    )


def change_record(scenario_id: str, edit_mode: str = "direct") -> ScenarioChangeRecord:
    return ScenarioChangeRecord(
        scenario_id=scenario_id,
        branch_id="101",
        branch_name="غدیر",
        indicator_key="avg_deposits",
        baseline_value=100.0,
        scenario_value=110.0,
        absolute_change=10.0,
        percentage_change=10.0,
        edit_mode=edit_mode,
    )


def result_record(scenario_id: str) -> ScenarioResultSummary:
    return ScenarioResultSummary(
        scenario_id=scenario_id,
        branch_id="101",
        baseline_score=500.0,
        scenario_score=520.0,
        baseline_rank=20,
        scenario_rank=17,
        baseline_grade="Grade 2",
        scenario_grade="Grade 1",
        rank_change=3,
        score_change=20.0,
    )


@pytest.fixture
def repository(tmp_path: Path) -> SQLiteScenarioRepository:
    return SQLiteScenarioRepository(tmp_path / "scenarios.db")


def test_repository_implementations_match_protocol_signatures() -> None:
    methods = (
        "create_scenario",
        "update_scenario",
        "get_scenario",
        "list_scenarios",
        "delete_scenario",
        "archive_scenario",
        "copy_scenario",
    )
    for method_name in methods:
        expected = inspect.signature(getattr(ScenarioRepository, method_name))
        assert inspect.signature(getattr(SQLiteScenarioRepository, method_name)) == expected
        assert inspect.signature(getattr(SqlServerScenarioRepository, method_name)) == expected


def test_create_always_persists_private_visibility(
    repository: SQLiteScenarioRepository,
) -> None:
    source = scenario_record(visibility="shared")
    created = repository.create_scenario(source, [change_record(source.scenario_id)])
    assert created.visibility == "private"
    assert created.row_version == 1


def test_private_and_legacy_shared_scenarios_are_owner_only(
    repository: SQLiteScenarioRepository,
) -> None:
    private = scenario_record()
    shared = scenario_record(visibility="shared")
    repository.create_scenario(private, [])
    repository.create_scenario(shared, [])
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE scenario_header SET visibility = 'shared' WHERE scenario_id = ?",
            (shared.scenario_id,),
        )
    assert repository.get_scenario(private.scenario_id, "user.one")[0].scenario_id == private.scenario_id
    with pytest.raises(AuthorizationError):
        repository.get_scenario(private.scenario_id, "user.two")
    assert repository.get_scenario(shared.scenario_id, "user.one")[0].scenario_id == shared.scenario_id
    with pytest.raises(AuthorizationError):
        repository.get_scenario(shared.scenario_id, "user.two")


def test_owner_update_and_stale_version(repository: SQLiteScenarioRepository) -> None:
    source = scenario_record()
    created = repository.create_scenario(source, [])
    updated_input = replace(created, scenario_name="نام جدید", visibility="shared")
    updated = repository.update_scenario(
        updated_input, [], expected_row_version=1, requesting_user_id="user.one"
    )
    assert updated.scenario_name == "نام جدید"
    assert updated.visibility == "private"
    assert updated.row_version == 2
    with pytest.raises(ConcurrencyError):
        repository.update_scenario(
            updated, [], expected_row_version=1, requesting_user_id="user.one"
        )


def test_non_owner_cannot_update_even_with_forged_owner_record(
    repository: SQLiteScenarioRepository,
) -> None:
    created = repository.create_scenario(scenario_record(), [])
    with pytest.raises(AuthorizationError):
        repository.update_scenario(
            replace(created, scenario_name="ویرایش غیرمجاز"),
            [],
            expected_row_version=1,
            requesting_user_id="user.two",
        )


def test_list_query_filters_by_owner_in_sql(repository: SQLiteScenarioRepository) -> None:
    own = repository.create_scenario(scenario_record(owner="user.one"), [])
    repository.create_scenario(scenario_record(owner="user.two"), [])
    listed = repository.list_scenarios("user.one")
    assert [item.scenario_id for item in listed] == [own.scenario_id]


def test_owner_archive_and_delete_and_non_owner_denied(
    repository: SQLiteScenarioRepository,
) -> None:
    first = repository.create_scenario(scenario_record(), [])
    with pytest.raises(AuthorizationError):
        repository.delete_scenario(first.scenario_id, "user.two", 1)
    archived = repository.archive_scenario(first.scenario_id, "user.one", 1)
    assert archived.status == "archived"
    assert archived.row_version == 2
    repository.delete_scenario(first.scenario_id, "user.one", 2)
    with pytest.raises(NotFoundError):
        repository.get_scenario(first.scenario_id, "user.one")


def test_non_owner_cannot_copy_legacy_shared_scenario(
    repository: SQLiteScenarioRepository,
) -> None:
    source = scenario_record(visibility="shared", status="executed")
    repository.create_scenario(
        source, [change_record(source.scenario_id)], [result_record(source.scenario_id)]
    )
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE scenario_header SET visibility = 'shared' WHERE scenario_id = ?",
            (source.scenario_id,),
        )
    with pytest.raises(AuthorizationError):
        repository.copy_scenario(
            source.scenario_id, "user.two", "کاربر دو", "نسخه کاربر دو"
        )
    copied = repository.copy_scenario(
        source.scenario_id, "user.one", "کاربر یک", "نسخه کاربر یک"
    )
    assert copied.scenario_id != source.scenario_id
    assert copied.owner_user_id == "user.one"
    assert copied.visibility == "private"
    loaded, changes, results = repository.get_scenario(copied.scenario_id, "user.one")
    assert loaded.scenario_name == "نسخه کاربر یک"
    assert len(changes) == 1
    assert len(results) == 1


def test_changes_and_result_summaries_are_persisted(
    repository: SQLiteScenarioRepository,
) -> None:
    source = scenario_record(status="executed")
    repository.create_scenario(
        source, [change_record(source.scenario_id)], [result_record(source.scenario_id)]
    )
    _, changes, results = repository.get_scenario(source.scenario_id, "user.one")
    assert changes == [change_record(source.scenario_id)]
    assert results == [result_record(source.scenario_id)]


def test_draft_update_preserves_existing_result_summaries_when_not_replaced(
    repository: SQLiteScenarioRepository,
) -> None:
    source = scenario_record(status="executed")
    created = repository.create_scenario(
        source, [change_record(source.scenario_id)], [result_record(source.scenario_id)]
    )
    updated = repository.update_scenario(
        replace(created, status="draft"),
        [],
        expected_row_version=1,
        result_summaries=None,
        requesting_user_id="user.one",
    )

    _, _, results = repository.get_scenario(updated.scenario_id, "user.one")

    assert updated.status == "draft"
    assert results == [result_record(source.scenario_id)]


def test_indicator_edit_mode_is_persisted(repository: SQLiteScenarioRepository) -> None:
    source = scenario_record()
    repository.create_scenario(
        source, [change_record(source.scenario_id, edit_mode="percent")]
    )
    _, changes, _ = repository.get_scenario(source.scenario_id, "user.one")
    assert changes[0].edit_mode == "percent"


def test_existing_database_migrates_edit_mode_with_direct_default(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE scenario_change (
                scenario_id TEXT NOT NULL,
                branch_id TEXT NOT NULL,
                branch_name TEXT NOT NULL,
                indicator_key TEXT NOT NULL,
                baseline_value REAL NOT NULL,
                scenario_value REAL NOT NULL,
                absolute_change REAL NOT NULL,
                percentage_change REAL,
                PRIMARY KEY (scenario_id, branch_id, indicator_key)
            )
            """
        )
        connection.execute(
            "INSERT INTO scenario_change VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("legacy", "101", "غدیر", "avg_deposits", 100.0, 110.0, 10.0, 10.0),
        )
    SQLiteScenarioRepository(database)
    with sqlite3.connect(database) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(scenario_change)")]
        mode = connection.execute(
            "SELECT edit_mode FROM scenario_change WHERE scenario_id = 'legacy'"
        ).fetchone()[0]
    assert "edit_mode" in columns
    assert mode == "direct"


def test_list_query_loads_headers_only(tmp_path: Path) -> None:
    class TracedRepository(SQLiteScenarioRepository):
        queries: list[str]

        def __init__(self, path: Path) -> None:
            self.queries = []
            super().__init__(path)

        @contextmanager
        def _connection(self):
            with super()._connection() as connection:
                connection.set_trace_callback(self.queries.append)
                yield connection

    repository = TracedRepository(tmp_path / "trace.db")
    source = scenario_record()
    repository.create_scenario(source, [change_record(source.scenario_id)])
    repository.queries.clear()
    listed = repository.list_scenarios("user.one", search="آزمون", limit=25)
    assert len(listed) == 1
    select_queries = [query.lower() for query in repository.queries if query.lstrip().lower().startswith("select")]
    assert select_queries
    assert any("owner_user_id = 'user.one'" in query for query in select_queries)
    assert all("scenario_change" not in query for query in select_queries)
    assert all("scenario_result_summary" not in query for query in select_queries)


def test_audit_log_records_lifecycle_actions(
    repository: SQLiteScenarioRepository,
) -> None:
    source = scenario_record(visibility="shared")
    created = repository.create_scenario(source, [])
    updated = repository.update_scenario(
        replace(created, scenario_name="ویرایش‌شده"), [], expected_row_version=1,
        requesting_user_id="user.one",
    )
    copied = repository.copy_scenario(
        updated.scenario_id, "user.one", "کاربر یک", "کپی"
    )
    archived = repository.archive_scenario(updated.scenario_id, "user.one", 2)
    repository.delete_scenario(archived.scenario_id, "user.one", 3)
    with sqlite3.connect(repository.database_path) as connection:
        actions = [
            row[0]
            for row in connection.execute(
                "SELECT action FROM scenario_audit_log ORDER BY audit_id"
            )
        ]
    assert {"create", "update", "copy", "archive", "delete"}.issubset(actions)
    assert copied.scenario_id


def test_local_user_config_loads(tmp_path: Path) -> None:
    path = tmp_path / "user.json"
    path.write_text(
        json.dumps(
            {"user_id": "test.user", "display_name": "کاربر تست", "roles": ["branch_user"]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    user = load_current_user(path)
    assert user.user_id == "test.user"
    assert user.display_name == "کاربر تست"
    assert user.roles == ("branch_user",)


def test_local_user_config_supports_assigned_branch(tmp_path: Path) -> None:
    path = tmp_path / "branch-user.json"
    path.write_text(
        json.dumps(
            {
                "user_id": "branch.user",
                "display_name": "کاربر شعبه",
                "roles": ["branch_user"],
                "branch_id": "00101",
                "branch_code": "101",
                "branch_name": "شعبه مرکزی",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    user = load_current_user(path)
    assert (user.branch_id, user.branch_code, user.branch_name) == (
        "00101",
        "101",
        "شعبه مرکزی",
    )


def test_project_local_user_config_loads() -> None:
    root = Path(__file__).resolve().parents[1]
    user = load_current_user(root / "config" / "local_user.json")
    assert user.user_id == "demo.user"
    assert user.display_name == "کاربر آزمایشی"
    assert "branch_user" in user.roles
    assert user.branch_id == "2001"
    assert user.branch_code == "2001"
    assert user.branch_name == "خیابان امام زنجان"
