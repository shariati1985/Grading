# Integration Contract

## 1. Objective
This document identifies the production integration boundaries that Bank IT must implement around the handover source. It separates approved business/model behavior from environment-specific technical integration.

## 2. Integration boundaries

| Boundary | Current prototype | Production target | Status in handover |
|---|---|---|---|
| Authentication | Local user file | Active Directory (AD) | Enterprise adapter pending |
| Organizational access context | Local user metadata | HRM | HRM adapter pending |
| Branch master, region hierarchy & grading data | Local Excel workbook | Branch Grading Dashboard Database | Adapter point exists; production DB implementation pending |
| Scenario persistence | Local SQLite | Sensitivity Analysis SQL Server Database | Contract/skeleton present; implementation pending |
| Runtime configuration | Local defaults / environment | Bank deployment & secret management | Externalized |
| Logging / audit / monitoring | Local application behavior | Central bank services | Required from Bank IT |

## 3. Production source-system architecture

The agreed production architecture uses three authoritative external sources:

- **AD** for authentication.
- **HRM** for organizational structure used to determine the user's access scope.
- **Branch Grading Dashboard Database** for branch master data, regions, branch-to-region/subordinate relationships, indicators, scores, ranks, grades, periods/history, and dashboard analytics.

HRM must not be used as the source of branch hierarchy for grading analysis. Once HRM determines whether the user is branch-level, region-level, or head-office, the actual permitted branch set is resolved from the Branch Grading Dashboard Database.

Saved scenarios are stored separately in the Sensitivity Analysis Database and remain private to their owner.

See `docs/ACCESS_CONTROL_CONTRACT.md`.

## 4. Branch grading dashboard database integration

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

## 5. Scenario persistence integration

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

## 6. Identity and HRM integration

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
With `AUTH_MODE=enterprise`, Bank IT must authenticate the user through AD and map that identity into the application's `CurrentUser` contract.

A separate HRM adapter must then resolve the authenticated user's organizational placement for Data Scope determination. The normalized application scope is `branch`, `region`, or `head_office`.

The concrete AD/HRM protocol, field names, endpoints, tables, and credentials are intentionally not assumed by this handover and must be supplied by Bank IT.

Runtime settings:
- `AUTH_MODE=enterprise`
- `AUTH_ISSUER_URL`
- `AUTH_CLIENT_ID`
- secret/client credentials through the bank's approved secret-management mechanism where required.

The exact enterprise identity technology is not defined by the current source and must be selected by Bank IT.

## 7. Authorization
Authentication and authorization must remain separate concerns.

The agreed Data Scope rules are:
- branch user -> own branch only;
- region user -> branches subordinate to that region;
- head-office user -> entire branch network.

The user's organizational scope comes from HRM; the permitted branch IDs and region/subordinate hierarchy come from the Branch Grading Dashboard Database.

Functional role permissions are separate from Data Scope.

Saved-scenario visibility is also separate: every normal user sees and manages only scenarios where `owner_user_id` equals the authenticated user's ID. Organization hierarchy does not grant visibility to another user's scenarios.

No integration implementation may assume that successful authentication automatically grants access to all branches or to another user's scenarios.

## 8. Configuration and secrets
Production configuration must be injected externally. Real values must not be committed to Git.

The handover template is `.env.example`. It documents names only and contains no production credentials.

Required production values include:
- application environment/version;
- baseline period;
- data-source type and connection endpoint;
- scenario database type and connection endpoint;
- authentication mode and identity endpoint.

## 9. Error behavior
Production adapters must not silently fall back from:
- SQL Server to Excel;
- enterprise authentication to local user;
- SQL Server persistence to SQLite.

A missing/unimplemented production adapter must fail explicitly. This is intentional to avoid running the bank deployment against local prototype components by mistake.

## 10. Security expectations
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

## 11. Integration acceptance criteria
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

## 12. Ownership
- Business owner: grading rules, indicator meaning, weights, scenario semantics, access-policy approval, UAT approval.
- Bank IT: infrastructure, production adapters, SSO, database implementation, security, deployment, monitoring, backup, operational support.
- Any change crossing the business/technical boundary must be documented and approved before production release.
