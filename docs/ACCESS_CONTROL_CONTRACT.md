# Access Control & Data Scope Contract

## 1. Final agreed access model
Access has two independent dimensions and they must not be mixed:

1. **Data Scope** — which branches' grading data the user may view/analyze.
2. **Scenario Ownership** — which saved scenarios the user may view/manage.

## 2. Source systems

### Active Directory (AD)
AD is the authentication source. It establishes the authenticated enterprise identity.

### HRM
HRM is the authoritative source for the user's organizational placement and structure used to determine access scope.

HRM is **not** the source of branch master data or branch-to-region hierarchy for this application.

### Branch Grading Dashboard Database
The grading-dashboard database is the authoritative source for:
- branches;
- regions;
- branch-to-region/subordinate-branch relationships;
- grading indicators;
- scores;
- ranks;
- grades;
- grading periods/history;
- network-level dashboard information.

### Sensitivity Analysis Database
The sensitivity-analysis database stores:
- scenarios;
- scenario versions;
- changes;
- results;
- owner identity;
- audit trail.

## 3. Data Scope rule
The HRM adapter must translate the authenticated user's organizational placement into one of these application scope levels:

| Scope level | Allowed grading data |
|---|---|
| `branch` | Only the user's own branch |
| `region` | All branches subordinate to the user's region |
| `head_office` | All branches in the network |

The actual branch list for a region must be resolved from the **grading-dashboard database**, not HRM.

Therefore the flow is:

```text
AD -> authenticated identity
   -> HRM -> organizational scope level + organization reference
   -> Grading Dashboard DB -> permitted branch IDs
   -> Sensitivity Analysis application
```

## 4. Scenario Ownership rule
Saved scenarios are private to their creator.

For every normal user:
- list: only scenarios where `owner_user_id = current_user.user_id`;
- read: only owned scenarios;
- update: only owned scenarios;
- execute/save result: only owned scenarios;
- archive: only owned scenarios;
- delete: only owned scenarios;
- create-new-version/copy: source scenario must be owned by the same user.

A branch manager cannot see another user's scenarios in the same branch.
A regional user cannot see scenarios created by users in subordinate branches.
A head-office user cannot see another user's scenarios merely because the user has network-wide data scope.

No inherited scenario visibility exists through organizational hierarchy.

## 5. Separation of Role and Scope
A user's functional role and data scope are independent.

Examples:
- a head-office Viewer may see network-wide grading data but may have read-only application functions;
- a head-office Analyst may have the same data scope but may create/run scenarios;
- a branch Analyst may create scenarios only with branch-level data scope.

Final functional roles can be defined separately. They must not change the Scenario Ownership rule unless an explicit future privileged role is approved.

## 6. Application-level organization context
The HRM integration should normalize the user's organizational placement into an application contract equivalent to:

```text
user_id
organization_scope_level = branch | region | head_office
organization_reference
```

Where:
- for `branch`, the reference identifies the user's branch;
- for `region`, the reference identifies the user's region;
- for `head_office`, no branch restriction is applied.

The concrete HRM fields/API/table names remain an IT integration decision and are not assumed by this handover.

## 7. Enforcement requirements
Data scope must be enforced server-side/application-side before presenting data to the UI. Hiding UI controls alone is not authorization.

At minimum:
- dashboard queries must be restricted to permitted branch IDs;
- scenario builders may select only permitted branch IDs;
- persisted scenarios must not be loadable by another user ID;
- direct URL/query-parameter access must not bypass scope/ownership;
- audit logs must record user ID and relevant scenario actions.

## 8. Current implementation status
Scenario ownership is already enforced in the local SQLite implementation and service layer through `owner_user_id/requesting_user_id`.

HRM-based Data Scope resolution is a production integration point. The handover code includes a pure application-level scope contract/resolver; Bank IT must implement the HRM adapter and grading-dashboard hierarchy repository that provide its inputs.

## 9. Future privileged access
If the bank later requires Audit/Admin access to other users' scenarios, this must be introduced as a separate explicitly approved permission. It must not be inferred from branch/region/head-office Data Scope.
