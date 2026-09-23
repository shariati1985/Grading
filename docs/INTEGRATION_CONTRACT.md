# Integration Contract

## 1. Objective
This document identifies the production integration boundaries that Bank IT must implement around the handover source. It separates approved business/model behavior from environment-specific technical integration.

## 2. Integration boundaries

| Boundary | Current prototype | Production target | Status in handover |
|---|---|---|---|
| Branch grading input | Local Excel workbook | Bank-approved SQL/API/DWH source | Adapter point created; SQL implementation pending |
| Scenario persistence | Local SQLite | SQL Server | Contract/skeleton present; implementation pending |
| User identity | Local JSON user file | Enterprise identity/SSO | Adapter point created; enterprise implementation pending |
| Runtime configuration | Local defaults / environment | Bank deployment & secret management | Externalized |
| Logging / audit / monitoring | Local application behavior | Central bank services | Required from Bank IT |

## 3. Branch-data integration

### Application contract
The application calls:

```python
load_branch_data(period: str | None) -> DataFrame
```

The returned dataframe must conform exactly to `docs/DATA_CONTRACT.md`.

### Current production skeleton
`SqlServerBranchRepository` exists as the SQL Server adapter boundary. It currently raises `NotImplementedError` until Bank IT selects the approved driver/query strategy.

Runtime settings:
- `DATA_SOURCE_TYPE=sqlserver`
- `DATA_SOURCE_CONNECTION_STRING`
- `DATA_SOURCE_TABLE_OR_VIEW`
- `BASE_PERIOD`

### Recommended implementation responsibilities
The implementation should:
- use parameterized SQL or an approved ORM/driver;
- filter by the requested period where the source is multi-period;
- return only the canonical branch schema;
- preserve branch identifiers as text;
- avoid embedding credentials in source;
- fail clearly on connection/schema errors;
- support operational timeout and logging standards required by the bank.

The choice of DB view, stored procedure, API, ESB, or DWH endpoint is an infrastructure/integration decision for Bank IT, provided the application contract is preserved.

## 4. Scenario persistence integration

### Current prototype
Local scenarios are stored in SQLite.

### Production boundary
`SqlServerScenarioRepository` defines the required repository operations:
- create scenario;
- update scenario;
- get scenario;
- list scenarios;
- delete scenario;
- archive scenario;
- copy scenario.

The production implementation must preserve:
- ownership checks;
- requesting-user context;
- optimistic concurrency using row version;
- atomic updates;
- server-side list pagination;
- persisted scenario changes;
- persisted result summaries.

The existing SQL Server class is intentionally a skeleton and must not be represented as a completed production repository.

Runtime settings:
- `SCENARIO_DB_TYPE=sqlserver`
- `SCENARIO_DB_CONNECTION_STRING`

## 5. Identity integration

### Current prototype
`CurrentUser` contains:
- `user_id`
- `display_name`
- `roles`
- optional `branch_id`
- optional `branch_code`
- optional `branch_name`

The local implementation reads this object from `config/local_user.json`.

### Production target
With `AUTH_MODE=enterprise`, Bank IT must implement an adapter that maps the authenticated enterprise identity into the existing `CurrentUser` contract.

Runtime settings:
- `AUTH_MODE=enterprise`
- `AUTH_ISSUER_URL`
- `AUTH_CLIENT_ID`
- secret/client credentials through the bank's approved secret-management mechanism where required.

The exact enterprise identity technology is not defined by the current source and must be selected by Bank IT.

## 6. Authorization
Authentication and authorization must remain separate concerns.

The current user contract already carries `roles` and optional branch context, but the final production role matrix and data-scope rules must be approved by the business owner and then enforced by the application/integration layer.

No integration implementation may assume that successful authentication automatically grants access to all branches or all scenario operations.

## 7. Configuration and secrets
Production configuration must be injected externally. Real values must not be committed to Git.

The handover template is `.env.example`. It documents names only and contains no production credentials.

Required production values include:
- application environment/version;
- baseline period;
- data-source type and connection endpoint;
- scenario database type and connection endpoint;
- authentication mode and identity endpoint.

## 8. Error behavior
Production adapters must not silently fall back from:
- SQL Server to Excel;
- enterprise authentication to local user;
- SQL Server persistence to SQLite.

A missing/unimplemented production adapter must fail explicitly. This is intentional to avoid running the bank deployment against local prototype components by mistake.

## 9. Security expectations
Bank IT must apply the bank's security standards for:
- TLS/HTTPS;
- network segmentation/firewall rules;
- service accounts;
- least privilege;
- credential rotation;
- secret storage;
- database permissions;
- application/session security;
- audit logs;
- vulnerability assessment;
- backup and restore.

These controls are infrastructure requirements and are not fully implemented by the handover prototype.

## 10. Integration acceptance criteria
An integration is acceptable for UAT when:
1. the application starts without local production-data files;
2. enterprise identity resolves to the application user contract;
3. approved users can access only permitted functions/data;
4. branch data loads from the approved source for the requested period;
5. model output matches the approved baseline for an identical population;
6. scenarios persist across application restarts;
7. SQL Server concurrency/ownership rules work under multi-user access;
8. configuration contains no committed secrets;
9. integration failures are logged and visible to operations;
10. business UAT passes without changing approved calculation semantics.

## 11. Ownership
- Business owner: grading rules, indicator meaning, weights, scenario semantics, access-policy approval, UAT approval.
- Bank IT: infrastructure, production adapters, SSO, database implementation, security, deployment, monitoring, backup, operational support.
- Any change crossing the business/technical boundary must be documented and approved before production release.
