# Scenario persistence architecture

## Why files are not the scenario store

JSON, CSV, and per-user ad-hoc files do not provide atomic multi-table writes,
ownership enforcement, indexed queries, optimistic concurrency, or durable audit
history. Streamlit session state is process-local and may disappear on refresh,
restart, failover, or load balancing. It remains useful for the scenario currently
being edited, but it is not the system of record.

## Local SQLite architecture

The prototype uses `storage/scenarios.db` through `SQLiteScenarioRepository`.
The repository opens a context-managed connection for each operation, enables
foreign keys, uses parameterized SQL, keeps write transactions short, configures
WAL mode and a busy timeout, and closes every connection after use.

The normalized tables are:

- `scenario_header`: identity, owner, status, visibility, versions, timestamps,
  selected branch IDs, compact JSON summary, and optimistic `row_version`.
- `scenario_change`: only changed branch/indicator values, including the editor's
  authoritative `edit_mode` (`percent` or `direct`).
- `scenario_result_summary`: only selected-branch baseline/scenario summaries.
- `scenario_audit_log`: append-only lifecycle actions and row-version transitions.

Full baseline or scenario network DataFrames are intentionally not persisted.
List operations query only `scenario_header`; changes and selected summaries load
only when a scenario is opened. Lists default to 25 headers, support search and
status filtering, and cap a request at 100 rows.

SQLite is appropriate for a single-host local prototype. It is not the production
database for approximately 600 concurrent bank users.

The SQLite migration adds `scenario_change.edit_mode` idempotently. Existing rows
receive `direct`, preserving the historical behavior where the stored scenario
value was authoritative; newly saved rows retain the user's selected method.

## SQL Server migration

Production deployment should replace repository composition with
`SqlServerScenarioRepository` after implementing it with approved pyodbc or
SQLAlchemy dependencies. The public repository contract remains unchanged.

SQL Server should provide equivalents of `ScenarioHeader`, `ScenarioChange`,
`ScenarioResultSummary`, and `ScenarioAuditLog`, with foreign keys and indexes on
owner, visibility, status, created/updated time, and scenario identity. Stored
procedures or parameterized queries should:

- create a header, changes, summaries, and audit rows in one transaction;
- update/archive/delete with `WHERE RowVersion = @ExpectedRowVersion`;
- return the new row version atomically;
- enforce owner/visibility rules at the service/repository boundary;
- paginate and search headers server-side;
- retrieve change and result rows only for one authorized scenario.

For SQL Server, a native `rowversion` column can be exposed as an opaque version,
or the current integer contract can be maintained with an atomic increment.

## Concurrency strategy

Every scenario starts at `row_version = 1`. Update and archive increment it.
Update, archive, and delete require the caller's expected version. A mismatch
raises `ConcurrencyError`; the UI tells the user to reload instead of silently
overwriting another session. Copy always creates a new UUID and version 1.

SQLite uses `BEGIN IMMEDIATE` only for the brief mutation transaction. Production
SQL Server should use normal row-level locking and atomic version predicates.

## Ownership and visibility

- `private`: readable only by the owner.
- `shared`: readable by authenticated users.
- update, archive, and delete: owner only.
- shared scenarios owned by another user: open or copy only.
- copy: creates a new private scenario owned by the requesting user.

The local `CurrentUser` is loaded from `config/local_user.json`. This adapter is
deliberately separate from UI pages so Active Directory/SSO claims can replace it
without changing repositories or scenario calculations.

## Audit logging

The audit log records create, update, execute, archive, delete, and copy actions.
Each row contains the acting user, UTC timestamp, old/new row versions, scenario
ID, and compact JSON details. Audit rows are retained after scenario deletion.
Production retention, immutability, access, and forwarding to the bank audit/SIEM
platform should follow institutional policy.

## Deployment considerations for approximately 600 users

- Use SQL Server, not the prototype SQLite database.
- Run schema migrations as a controlled deployment step.
- Use connection pooling, encrypted connections, least-privilege service accounts,
  database backups, monitoring, and tested restore procedures.
- Resolve user identity through SSO/Active Directory and never trust editable UI
  owner fields.
- Keep header pagination and search server-side.
- Apply authorization on every individual read and mutation.
- Configure audit retention and operational telemetry.
- Use multiple Streamlit workers only with the shared SQL Server system of record;
  session state must remain an editing cache, never permanent storage.
