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
SQLAlchemy dependencies. The repository contract requires the requesting user
for every ownership-sensitive operation.

SQL Server should provide equivalents of `ScenarioHeader`, `ScenarioChange`,
`ScenarioResultSummary`, and `ScenarioAuditLog`, with foreign keys and indexes on
owner, visibility, status, created/updated time, and scenario identity. Stored
procedures or parameterized queries should:

- create a header, changes, summaries, and audit rows in one transaction;
- update/archive/delete with `WHERE RowVersion = @ExpectedRowVersion`;
- return the new row version atomically;
- enforce owner-only rules at the service and repository boundaries;
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

- every scenario operation is restricted to its owner;
- list queries filter by `owner_user_id` in the database query;
- create, update, and copy always persist `visibility = 'private'`;
- the visibility column remains temporarily for backward compatibility only;
- legacy rows marked `shared` receive no broader access and remain owner-only.

The local `CurrentUser` is loaded from `config/local_user.json`. This adapter is
deliberately separate from UI pages so Active Directory/SSO claims can replace it
without changing repositories or scenario calculations.

## Scenario selection scope

`SelectionScope` defines the four supported editing scopes: the user's assigned
branch, manually selected branches, selected regions, and all branches. The pure
`SelectionResolver` converts a scope and baseline branch metadata into an ordered,
deduplicated list of active branch IDs. It does not run calculations or access
persistence or Streamlit.

Selection affects only which branch rows are exposed for editing. The scenario
workflow still applies those edits to a copy of the complete baseline dataset and
reruns the ranking model for the full bank. Saved scenarios retain their resolved
branch IDs; because older records do not store scope metadata, they reopen as
`SELECTED_BRANCHES`.

## Bulk rules and manual overrides

The pure `ScenarioRuleEngine` expands independent indicator rules for resolved
branch IDs. Manual overrides take precedence over bulk rules, which take
precedence over baseline values. The engine produces structured preview rows,
validation issues, and canonical `ScenarioChange` records; ranking, persistence,
selection, authorization, and Streamlit remain outside it.

`INDICATOR_REGISTRY` is authoritative for the eight canonical indicator keys and
their value domains. `profit_loss` permits any finite value; the other seven
indicators have a minimum of zero. Values are not clamped or rounded by the rule
engine.

Rule definitions are stored in the existing scenario summary JSON under
`scenario_definition`, including schema version, scope and selection inputs,
operations, signed inputs, overrides, and validation status. This avoids a schema
migration. Older scenarios are reconstructed as `SET_VALUE` manual overrides so
their persisted branch-level final values are not reinterpreted.

Manual overrides are displayed as branch groups with stable UUID `group_id`
values. A user selects the branch once and configures all eight indicators in one
form. Each persisted domain row also retains a stable UUID `row_id`. Widget
identity, group editing, and deletion never use list position. Duplicate
validation applies only to `(branch_id, indicator_key)`; one branch may therefore
carry independent overrides for all eight indicators.

The centered scenario definition uses `scenario_mode` with either
`ONLY_USER_BRANCH` or `USER_AND_OTHERS`. `focus_branch_id` and
`focus_branch_source` distinguish an assigned user branch from a staff-selected
branch without creating separate organizational user types. Focus-branch
overrides are persisted separately from network bulk rules and branch exceptions.
The network scope contains only other branches, enforcing the effective
precedence `focus_branch_override > branch_exception > network_bulk_rule > baseline`.

Profit/Loss (`profit_loss`) preserves its signed raw value and uses raw min–max
benefit normalization: `((x - min) / (max - min)) * 999 + 1`. This produces the
same documented 1–1000 normalized scale as every other indicator. Its weighted
contribution is the normalized score multiplied by `0.03`; raw, normalized, and
weighted values remain separately labeled.

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
