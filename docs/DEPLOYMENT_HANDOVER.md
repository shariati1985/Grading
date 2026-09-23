# Deployment & Production Handover

## 1. Handover baseline
This document applies to:
- Repository: `shariati1985/Grading`
- Branch: `handover/grading-sensitivity-v1.0.0`
- Version: `1.0.0`
- Baseline commit before handover preparation: `df1bedb5de3098d3db7c5def77782d942121669b`

The branch is intended as the controlled source-code package for transfer to Bank IT.

## 2. What is already implemented
The repository includes:
- Branch grading/ranking logic.
- Scenario execution and comparison logic.
- Branch-centric sensitivity analysis.
- Multi-branch scenarios.
- Target-rank scenarios.
- Scenario save/restore workflows.
- Streamlit UI and navigation.
- Local SQLite scenario persistence.
- Data contracts and repository abstractions.
- Automated tests covering core calculation, persistence, workflow and UI behavior.

## 3. Explicit pre-production limitations
The following items are not complete production capabilities and must not be treated as such:

### 3.1 Baseline data source
The current Streamlit application loads `Data.xlsx` from the project root. Production must replace this local-file dependency with the bank-approved data source/integration mechanism.

### 3.2 Scenario persistence
The local runtime composes `SQLiteScenarioRepository`. This is suitable for prototype/local use only.

A `SqlServerScenarioRepository` contract-compatible skeleton exists, but its methods are intentionally unimplemented. Bank IT must implement and test the SQL Server repository for multi-user production use.

### 3.3 Authentication and authorization
Enterprise authentication is not wired into the current runtime. Bank IT must integrate the bank identity mechanism and apply approved role/data-scope rules.

## 4. Required Bank IT work
1. Establish DEV / TEST / UAT / PROD environments.
2. Configure enterprise identity/authentication.
3. Implement role-based authorization and approved data scope.
4. Replace Excel baseline data access with approved API / DB view / DWH / integration layer.
5. Implement production SQL Server scenario persistence.
6. Externalize runtime configuration and secrets.
7. Configure HTTPS, reverse proxy, internal DNS and network controls.
8. Add centralized application logging and audit logging.
9. Add health monitoring and operational alerting.
10. Define backup, restore and disaster-recovery procedures.
11. Perform security review and vulnerability testing.
12. Run automated tests and agreed UAT scenarios.
13. Obtain business-owner approval before production release.

## 5. Business-rule ownership
The ranking, grading, normalization, weighting and scenario-calculation rules are business-owned. Production integration or technical refactoring must not silently change calculation semantics. Any intentional rule change requires explicit business approval and regression testing.

## 6. Data handling
Real bank data, credentials, secrets and production connection strings must be supplied outside source control through approved bank mechanisms.

The handover branch intentionally excludes:
- `Data.xlsx`
- generated `Branch_Ranking_New_Model.xlsx`
- local SQLite databases
- generated CSV/Power BI outputs
- local user configuration
- logs and environment secret files

## 7. Acceptance checks before production
At minimum verify:
- Baseline ranking output matches the approved reference results.
- Scenario calculations match the handover version.
- Save / restore / version workflows operate correctly under SQL Server.
- Concurrent-user behavior is tested.
- User permissions and data scope are enforced.
- Audit records are complete.
- No production secrets exist in source control.
- Monitoring and backup procedures are operational.
- UAT is signed off by the business owner.

## 8. Release-control recommendation
After Bank IT completes integration and UAT, create a controlled production release/tag derived from this handover branch. Do not deploy an arbitrary working branch to production.
