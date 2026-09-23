# Branch Grading Sensitivity Platform

## Release
- Handover version: **1.0.0**
- Handover branch: `handover/grading-sensitivity-v1.0.0`
- Baseline source branch: `feature/multi-branch-finalization`
- Baseline commit: `df1bedb5de3098d3db7c5def77782d942121669b`

## Purpose
This repository contains the current implementation of the branch grading sensitivity-analysis platform. It includes the ranking/scenario engines, Streamlit user interface, local prototype persistence, service layer, data-access layer, and automated tests.

## Current technical state
The application is a functional prototype / pre-production handover baseline. The business logic and user workflows are implemented, but the following production integrations remain the responsibility of Bank IT:

1. Enterprise authentication and authorization.
2. Production data-source integration in place of the local Excel baseline.
3. Production SQL Server scenario persistence.
4. Infrastructure, secrets management, logging, monitoring, backup, security hardening, and deployment.
5. Final UAT and production release controls.

## Main components
- `app.py`: Streamlit entry point.
- `engine/`: ranking, comparison, sensitivity and scenario logic.
- `domain/`: scenario contracts and domain structures.
- `services/`: application/workspace services.
- `data/`: data contracts and repositories.
- `persistence/`: local SQLite repository plus SQL Server production skeleton.
- `ui/`: reusable UI and presentation components.
- `pages/`: Streamlit pages.
- `tests/`: automated tests.
- `docs/`: architecture and handover documentation.

## Local prototype execution
1. Use Python 3.13 or a compatible supported Python version.
2. Create and activate a virtual environment.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Supply the local baseline file `Data.xlsx` at repository root.
5. Run:
   ```bash
   streamlit run app.py
   ```

> `Data.xlsx` is intentionally not part of the handover source branch. A sanitized test/sample data set should be provided separately if needed.

## Production boundary
The current `app.py` still reads the local Excel baseline and the local composition uses SQLite. These are explicit integration points, not hidden assumptions. Bank IT should replace/configure them for the production environment without changing the approved business rules.

See the handover documents:\n- `docs/DEPLOYMENT_HANDOVER.md` — production deployment checklist.\n- `docs/DATA_CONTRACT.md` — canonical input/output data contract.\n- `docs/INTEGRATION_CONTRACT.md` — production integration boundaries and acceptance criteria.

## Security
Do not commit passwords, tokens, connection strings, production certificates, or real bank data. Use environment/configuration management and the bank's approved secret-management mechanism.
