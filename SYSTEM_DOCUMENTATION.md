# OMDRRMO Naic Operations Dashboard

## System Handbook, User Guide, and Technical Reference

| Document field | Value |
|---|---|
| System | OMDRRMO Naic Operations Dashboard |
| Organization | Office of the Municipal Disaster Risk Reduction and Management, Naic |
| Document date | 26 August 2026 |
| Code snapshot | `phase/11d-cloud-pilot`, commit `22c3125`, including the inspected working-tree changes |
| Primary timezone | Asia/Manila |
| Current stage | Deployment candidate and controlled cloud-pilot preparation |

This handbook consolidates the system's user instructions, operational rules,
technology stack, architecture, administration, deployment, recovery,
troubleshooting, and known limitations. Phase-specific runbooks under
`deployment/` remain authoritative for their specialized procedures.

> This system supports disaster-response operations, but it does not replace
> official MDRRMO command decisions, source verification, approved emergency
> protocols, or legally required records-management procedures.

## Contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [Current capability and approval status](#2-current-capability-and-approval-status)
3. [Quick start for users](#3-quick-start-for-users)
4. [Roles and access](#4-roles-and-access)
5. [Operational concepts](#5-operational-concepts)
6. [Complete page guide](#6-complete-page-guide)
7. [End-to-end operating workflows](#7-end-to-end-operating-workflows)
8. [Validation and data-integrity rules](#8-validation-and-data-integrity-rules)
9. [Technology stack](#9-technology-stack)
10. [Architecture and data model](#10-architecture-and-data-model)
11. [Local installation and configuration](#11-local-installation-and-configuration)
12. [Cloud-pilot configuration](#12-cloud-pilot-configuration)
13. [Administration and maintenance](#13-administration-and-maintenance)
14. [Backup and recovery](#14-backup-and-recovery)
15. [Security, privacy, and auditing](#15-security-privacy-and-auditing)
16. [Errors and troubleshooting](#16-errors-and-troubleshooting)
17. [Known limitations and unresolved decisions](#17-known-limitations-and-unresolved-decisions)
18. [Release and operational checklists](#18-release-and-operational-checklists)
19. [Repository map](#19-repository-map)
20. [Glossary](#20-glossary)

## 1. Purpose and scope

The dashboard provides one controlled workspace for:

- Google/OIDC sign-in and PostgreSQL-backed role authorization;
- disaster-event activation, escalation, stand-down, closure, and history;
- barangay situation and population reporting;
- evacuation-center registration, occupancy, vulnerable-group, supply, and
  cross-barangay monitoring;
- report validation, correction, resubmission, and source reconciliation;
- incident logging, lifecycle management, response-resource dispatch, and
  release;
- provisional and validated operational dashboards;
- immutable situation-report snapshots and Excel/PDF exports;
- user administration, system-health checks, immutable audit review, verified
  backups, and controlled recovery guidance.

The system is designed for current-event operations. Historical report
snapshots and audit records remain available even when no event is active.

## 2. Current capability and approval status

### 2.1 Implemented capabilities

The current code implements the major workflows listed in this handbook,
including incident persistence, event lifecycle controls, validation,
correction lineage, report exports, system auditing, backups, and recovery
validation.

The functional UAT sign-off dated 10 August 2026 records completion of:

- authentication and session testing;
- role and permission testing;
- event, barangay, evacuation, validation, incident, and reporting workflows;
- audit-trail behavior;
- backup creation and archive verification;
- database-outage, logging, reconnection, and transaction-rollback behavior.

### 2.2 What the UAT sign-off does not authorize

The sign-off does not itself approve production deployment. The following
remain environment- or management-owned decisions:

- authoritative barangay names, count, and PSGC codes;
- authoritative alert-level terminology and operational meaning;
- official MDRRMO Excel and PDF layouts;
- production hostname, HTTPS/TLS, reverse proxy, firewall, and network design;
- production Google OIDC callback registration;
- off-machine/off-site backup location, frequency, retention, and custodians;
- privacy, records-management, and third-party cloud approval;
- classification of existing data as test, official, mixed, or unknown.

### 2.3 Deployment profiles

| Profile | Intended use | Important behavior |
|---|---|---|
| `local` | Local development, UAT, or controlled office deployment | Local backup tools and archive views are available. |
| `cloud` | Restricted Streamlit Community Cloud and remote PostgreSQL pilot | PostgreSQL TLS is required, the pool is bounded, cloud budgets are checked, and in-app local backup creation is disabled. |

The cloud profile is a pilot profile, not automatic production approval.

## 3. Quick start for users

### 3.1 Sign in

1. Open the approved system address.
2. Select **Sign in**.
3. Complete Google/OIDC authentication.
4. The system matches the authenticated email to an active `app_users`
   record in PostgreSQL.
5. Only pages permitted for the assigned role appear in navigation.

Authentication and authorization are separate. A valid Google login is not
enough; an Administrator must authorize the same email in the application.

### 3.2 Normal operating sequence

1. An Operations Officer or Administrator creates or confirms the active event.
2. Encoders or Operations Officers submit barangay and evacuation-center data.
3. Validators or Operations Officers review submitted reports.
4. Operators investigate dashboard warnings and reconciliation differences.
5. Incident managers record incidents and coordinate response resources.
6. Authorized reporting users generate a provisional or validated snapshot.
7. Administrators monitor health, audit activity, and backup evidence.

### 3.3 Sign out

Use **Sign out** in the account area. If the OIDC token expires, the system
clears its authorization cache and requires a new sign-in.

### 3.4 Basic usage rules

- Use the information source and remarks fields to preserve operational context.
- Do not invent missing figures. Use the system's unknown or no-report options
  where available.
- Review the active event and SitRep context before every submission.
- Do not repeatedly click a submit button. Duplicate-submission protection is
  present, but one deliberate submission is the correct procedure.
- Treat reconciliation differences as warnings requiring investigation, not as
  permission to silently overwrite one source with another.
- Generate a new report snapshot after corrections; saved snapshots are
  immutable.

## 4. Roles and access

### 4.1 Role matrix

| Capability | Viewer | Executive | Encoder | Validator | Operations Officer | Administrator |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| View dashboard | Yes | Yes | Yes | Yes | Yes | Yes |
| View reports and exports | No | Yes | No | Yes | Yes | Yes |
| Manage disaster events | No | No | No | No | Yes | Yes |
| Submit barangay updates | No | No | Yes | No | Yes | Yes |
| Validate reports | No | No | No | Yes | Yes | Yes |
| Submit evacuation-center updates | No | No | Yes | No | Yes | Yes |
| Create/manage evacuation centers | No | No | No | No | Yes | Yes |
| Manage incidents and resources | No | No | No | No | Yes | Yes |
| Manage users | No | No | No | No | No | Yes |
| System Health & Audit | No | No | No | No | No | Yes |

### 4.2 Role guidance

- **Viewer:** dashboard-only situational awareness.
- **Executive:** dashboard plus saved reports and exports.
- **Encoder:** records barangay and evacuation-center information but cannot
  validate it.
- **Validator:** reviews barangay and evacuation-center reports and population
  reconciliation; cannot encode ordinary operational reports.
- **Operations Officer:** operates event, reporting, validation, evacuation,
  incident, and response-resource workspaces; cannot administer users.
- **Administrator:** full application access and system-custodian duties.

When staffing allows, the person who encodes a report should not validate the
same report. Assign the least-powerful role that supports the person's duties.

### 4.3 Account safeguards

- An Administrator cannot deactivate their own account.
- An Administrator cannot remove their own Administrator role.
- The final active Administrator cannot be removed or deactivated.
- Role and status changes are audited.
- Use dedicated accounts; do not repeatedly change one person's role during an
  active operation.

## 5. Operational concepts

### 5.1 Active disaster event

Operational records belong to one active disaster event. The database and
service layer enforce at most one active event. Close the current event before
creating another. Only an Administrator can reopen a closed event.

Event metadata includes:

- event name and hazard type;
- tropical-cyclone classification when applicable;
- WHITE, BLUE, or RED alert level;
- EOC status: Monitoring, Partially Activated, Activated, or Stand Down;
- SitRep number, official reference, situation overview, and event timestamps;
- reasons, authority references, and actor identity for changes.

For a tropical cyclone, enter only the storm name in the event-name field and
select its changing classification separately.

### 5.2 Affected population

**Total Reported Affected Population** means all people reported as impacted by
the disaster. It does not mean that everyone is injured, homeless, or evacuated.
It includes:

- people inside formal evacuation centers;
- displaced people staying outside formal evacuation centers; and
- other affected residents not recorded as currently evacuated.

The total affected population is therefore the overall figure. Inside-center
and outside-center values are subgroups and must not exceed the total.

### 5.3 Inside and outside evacuation centers

- **Inside evacuation centers:** families and individuals currently recorded
  in formal evacuation centers.
- **Outside evacuation centers:** displaced families and individuals staying
  elsewhere, such as with relatives, in temporary shelter, or another location.

Barangay and evacuation-center reports are independent operational sources.
Differences are shown for reconciliation rather than silently replaced.

### 5.4 Provisional versus official validated views

| Mode | Included source data | Appropriate use |
|---|---|---|
| Provisional Operational | Latest submitted, for-validation, or validated operational reports | Current response awareness; may contain unvalidated information. |
| Official Validated | Latest validated source reports only | Formal validated picture and official snapshot preparation. |

A saved snapshot retains the selected mode and source data at generation time.
Later corrections require a new snapshot.

### 5.5 Validation statuses

| Status | Meaning |
|---|---|
| Draft | Defined status for incomplete work; normal page submissions are saved as submitted reports. |
| Submitted | Awaiting review. |
| For Validation | In the pending review set. |
| Validated | Accepted by an authorized reviewer. |
| Needs Correction | Returned with correction instructions. |
| Superseded | Replaced by a corrected resubmission; retained in history. |

### 5.6 Reconciliation statuses

- **Matching Totals:** barangay and attributed evacuation-center figures agree.
- **Different Totals:** both sources exist but inside-center totals differ.
- **Missing Barangay Report:** an evacuation source exists without a current
  barangay report.
- **Missing Center Report:** a barangay reports inside-center occupants without
  a matching current center source.
- **Assignment Conflict:** cross-barangay allocations exceed or conflict with a
  center's reported totals.
- **No Current Data:** neither usable source currently provides figures.

## 6. Complete page guide

### 6.1 Dashboard

Available to every role.

The dashboard provides:

- a manual refresh control;
- Provisional Operational and Official Validated modes;
- active-event, alert, EOC, SitRep, and official-reference context;
- non-zero attention items for rescue, roads, power, water, center capacity,
  supplies, medical cases, validation, population consistency, and source
  reconciliation;
- the current affected and evacuation summary;
- reporting coverage and report freshness;
- barangay operational tables and charts;
- evacuation-center occupancy, capacity, supply, and medical status;
- report-consistency checks with source ages and differences.

When an attention item appears, expand its supporting-record list, locate the
named source record, and verify it in the corresponding operational page.

### 6.2 Event Control

Available to Operations Officers and Administrators.

Use Event Control to:

- create a new event when none is active;
- reopen a closed event as an Administrator;
- update event details and tropical-cyclone classification;
- change alert level with reason and authority reference;
- change EOC status;
- review event and alert history;
- close the active event with an explicit reason.

Important rules:

- only one active event is allowed;
- event start and change times must include timezone information;
- alert and lifecycle changes preserve actor and reason history;
- normal operational submissions require an active event;
- closed events cannot accept normal new operational reports.

### 6.3 Barangay Updates

Available to Encoders, Operations Officers, and Administrators.

Submission workflow:

1. Select the barangay.
2. Review the latest evacuation-center figures supplied as a reference.
3. Enter total affected families and individuals.
4. Enter inside-center and outside-center families and individuals.
5. Review the population-consistency calculation.
6. Enter situation, flood, road, utility, and rescue information.
7. Identify the source, add remarks, review, and submit.

If a report is marked **Needs Correction**, the form is prefilled from that
report. The corrected submission supersedes the returned report while retaining
the original and its review history.

### 6.4 Report Validation

Available to Validators, Operations Officers, and Administrators.

The page contains:

- a barangay validation queue;
- an evacuation-center validation queue;
- a population-reconciliation queue.

For each pending report:

1. inspect its source, time, figures, and remarks;
2. compare it with related operational records;
3. select **Validated** or **Needs Correction**;
4. provide correction instructions when returning a report;
5. submit the review once.

Correction instructions are mandatory for **Needs Correction**. A report that
another reviewer already processed cannot be reviewed again as pending.

### 6.5 Evacuation Centers

Available to Encoders for occupancy submissions and to Operations Officers or
Administrators for both submissions and center management.

The page supports:

- creation of evacuation-center master records;
- center status and occupancy updates;
- children, senior citizens, persons with disabilities, pregnant women, and
  medical-case counts;
- food, water, electricity, sanitation, source, and remarks;
- current cross-barangay allocations;
- recent report history.

Center statuses are Standby, Open, Full, Over Capacity, and Closed.

Cross-barangay allocation records attribute part of a center's occupants to an
origin barangay different from the host barangay. Use this only when the origin
and counts are verified. Allocation differences are reconciliation inputs, not
silent edits to either source report.

### 6.6 Incidents

Available to Operations Officers and Administrators.

Incident functions include:

- creating incidents with location, type, description, priority, persons
  affected, source, and reporter identity;
- selecting and inspecting active or historical incidents;
- changing priority with a recorded reason;
- advancing incident status;
- reopening terminal incidents under the controlled workflow;
- creating response-team, vehicle, and equipment resources;
- assigning and releasing resources;
- changing resource readiness;
- reviewing the recorded incident history and its corresponding immutable
  system-audit entries.

Incident priorities are Low, Moderate, High, and Critical.

Incident lifecycle:

```text
Reported -> For Verification -> Verified -> Team Dispatched -> Responding
         -> Resolved
         -> Cancelled
```

Forward stages may be skipped when urgent operations require it, but normal
status changes cannot move backward. Resolved and Cancelled are terminal until
the controlled reopen action is used.

Resource states are Available, Assigned, Maintenance, and Out of Service.
Assigned is controlled automatically by dispatch. Release an active assignment
before manually changing readiness.

### 6.7 Reports

Available to Executives, Validators, Operations Officers, and Administrators.

The page provides:

- current active-event and SitRep context;
- creation of immutable Provisional Operational or Official Validated snapshots;
- a historical snapshot archive;
- integrity-hash review;
- Excel and PDF downloads.

Before creating a snapshot:

1. confirm the active event and current SitRep number;
2. select the correct data mode;
3. review the warning for provisional data when applicable;
4. confirm authorization and generate once.

The system uses a generation token to ignore accidental duplicate requests.
Snapshots are append-only and protected from update or deletion by a PostgreSQL
trigger. Their SHA-256 hash is recalculated when retrieved; a mismatch blocks
use because the stored snapshot can no longer be trusted.

### 6.8 User Administration

Available only to Administrators.

Use this page to:

- review authorized users and role/status counts;
- authorize a new OIDC email identity;
- update display name, role, and active status;
- review the permissions assigned to each role.

An authorized user's email must match the email supplied by the OIDC provider.
Deactivation blocks access without deleting the audit history.

### 6.9 System Health & Audit

Available only to Administrators.

System Health checks include:

- PostgreSQL connectivity;
- active-event integrity;
- active Administrator availability;
- barangay master-data presence;
- snapshot and audit immutability triggers;
- database timezone;
- Alembic revision parity;
- required tables;
- local PostgreSQL backup tools and writable directories; or
- cloud TLS, connection budget, storage budget, and runtime-storage boundary.

Status meanings:

- **PASS:** the automated check passed;
- **WARN:** attention or external verification is required;
- **FAIL:** a required automated condition failed.

A page-level PASS does not complete manual production gates.

The Audit tab filters immutable database-trigger records by data area and
operation and displays before-and-after row state. The application has no audit
edit or delete control.

The Backup tab changes by deployment profile:

- local mode can create and inspect verified local archives;
- cloud mode provides provider-recovery, independent-archive, and isolated
  restore guidance but intentionally disables in-app archive creation.

## 7. End-to-end operating workflows

### 7.1 Start a new operation

1. Confirm that no event is active.
2. Create the event with official source information.
3. Confirm alert level, EOC status, classification, start time, and SitRep.
4. Confirm the event strip appears on each operational page.
5. Begin barangay, evacuation-center, and incident reporting.

### 7.2 Barangay reporting and correction

1. Encoder submits a source-attributed report.
2. The report enters the validator queue.
3. Validator accepts it or returns it with instructions.
4. A returned report prepopulates the next encoder form.
5. The corrected report links to and supersedes the original.
6. Validator reviews the new report.
7. Dashboard and official-mode data update according to validation status.

### 7.3 Evacuation reporting and reconciliation

1. Ensure the center master record exists with correct host barangay and safe
   capacity.
2. Submit status, occupancy, vulnerable groups, services, source, and remarks.
3. Record verified cross-barangay allocations where required.
4. Validate the center report.
5. Review barangay-versus-center differences in Report Validation or Dashboard.
6. Correct the responsible source; do not overwrite the other source merely to
   force a match.

### 7.4 Incident response

1. Create the incident under the active event.
2. Verify its classification, source, priority, and location.
3. Advance status as operations progress.
4. Assign only available resources.
5. Release resources when no longer attached to the incident.
6. Record actions and reasons in the lifecycle history.
7. Resolve or cancel the incident when authorized.

### 7.5 Issue a situation report

1. Review dashboard attention items and reconciliation warnings.
2. Confirm the event and SitRep number.
3. Select provisional or official validated mode.
4. Generate the immutable snapshot.
5. Verify the snapshot ID, mode, time, generator, and SHA-256 reference.
6. Download Excel and/or PDF.
7. Preserve the issued file according to office records policy.
8. Generate a new snapshot for later corrections.

### 7.6 Close an operation

1. Confirm reporting and unresolved incidents are appropriately handled.
2. Generate the required final snapshot.
3. Create and verify a database backup.
4. Copy the complete backup set to approved off-machine storage.
5. Close the active event with reason and authority reference.
6. Preserve audit, snapshot, UAT, and recovery evidence.

## 8. Validation and data-integrity rules

### 8.1 Population rules

- All counts must be zero or greater.
- Affected families cannot exceed affected individuals.
- Families inside centers cannot exceed individuals inside centers.
- Families outside centers cannot exceed individuals outside centers.
- Total displaced families cannot exceed affected families.
- Total displaced individuals cannot exceed affected individuals.
- Remaining affected families cannot exceed remaining affected individuals.
- Rescue-request counts cannot be negative.

### 8.2 Flood rules

- Flood depth cannot be negative.
- **No Flooding** requires a flood depth of zero centimeters.

### 8.3 Evacuation-center rules

- Families cannot exceed individuals.
- Each vulnerable-group or medical count cannot exceed total individuals.
- Standby and Closed centers must report zero occupants and zero vulnerable
  groups/medical cases.
- If safe capacity is positive and occupancy exceeds it, status must be
  **Over Capacity**.
- **Over Capacity** is invalid when occupancy does not exceed safe capacity.
- Cross-barangay allocated families cannot exceed allocated individuals.
- Allocations cannot exceed the center's current occupancy.

### 8.4 Event, incident, and resource rules

- At most one disaster event may be active.
- Event changes require an authorized active account.
- Persons affected by an incident cannot be negative.
- Normal incident lifecycle changes move forward only.
- Closed incidents cannot receive new resource assignments.
- A resource cannot have conflicting active assignments.
- Assigned status is controlled by dispatch, not manual readiness editing.

### 8.5 Submission and transaction safety

- Operational forms use canonical UUID submission keys.
- Duplicate keys are rejected or treated as already saved.
- Database writes use a transaction that commits on success and rolls back on
  failure.
- Correction resubmission preserves the previous row and marks it Superseded.

## 9. Technology stack

### 9.1 Core platform

| Layer | Technology | Inspected version or role |
|---|---|---|
| Language | Python | 3.14 deployment baseline |
| Web application | Streamlit | 1.61.0 |
| Database | PostgreSQL | Required relational database |
| ORM and SQL | SQLAlchemy | 2.0.51 |
| PostgreSQL driver | psycopg 3 | 3.3.4 |
| Schema migration | Alembic | 1.19.0 |
| Authentication | Streamlit OIDC with Google metadata | Authlib 1.7.2 and related libraries |
| Tabular processing | pandas | 3.0.5 |
| Charts | Plotly and Altair | 6.9.0 and 6.2.2 |
| Excel export | openpyxl | 3.1.5 |
| PDF export | ReportLab | 5.0.0 |
| Environment loading | python-dotenv | 1.2.2 |
| Timezone data | tzdata / `zoneinfo` | Asia/Manila display timezone |
| Testing | Python `unittest` | Repository regression and contract suite |
| Database backup | PostgreSQL `pg_dump` / `pg_restore` | External client tools |

All runtime packages are pinned in `requirements.txt`.

### 9.2 User interface

- Wide Streamlit layout with role-filtered navigation.
- Shared MDRRMO visual system in `utils/ui.py` and `styles/mdrrmo.css`.
- Light main workspace and dark branded sidebar.
- Responsive evacuation summary and operational tables.
- Plotly mode bar and scroll zoom disabled for routine dashboard charts.

## 10. Architecture and data model

### 10.1 Logical architecture

```text
User browser
    |
    v
HTTPS endpoint / Streamlit application
    |
    +--> Google OIDC authentication
    |
    +--> app.py role-based navigation
            |
            v
        pages/ presentation and forms
            |
            v
        services/ authorization, validation, transactions, business rules
            |
            v
        database/repositories.py and SQLAlchemy models
            |
            v
        PostgreSQL tables, constraints, indexes, and audit/immutability triggers
```

Recommended on-premises topology:

```text
Client browsers -> HTTPS reverse proxy -> Streamlit on 127.0.0.1 -> PostgreSQL
```

PostgreSQL should not be exposed to general office clients.

### 10.2 Code responsibilities

- `pages/`: UI rendering, forms, user messages, and page-level orchestration.
- `services/`: authorization checks, operational validation, transactions, and
  business errors.
- `database/repositories.py`: read/query operations.
- `database/models.py`: database entities, constraints, indexes, and relations.
- `database/migrations/`: versioned schema and trigger changes.
- `utils/`: authentication, formatting, logging, UI, view contracts, and export
  caching.
- `scripts/`: installation, verification, performance, deployment, backup, and
  recovery commands.

### 10.3 Main database entities

| Entity | Purpose |
|---|---|
| `alert_levels` | Alert-level master data. |
| `disaster_events` | Event identity, hazard, alert, EOC, SitRep, and active state. |
| `alert_level_history` | Alert transition history. |
| `event_change_history` | Event metadata and lifecycle changes. |
| `barangays` | Barangay and PSGC master data. |
| `barangay_updates` | Source-attributed barangay situation and population reports. |
| `evacuation_centers` | Center master records and safe capacity. |
| `evacuation_center_updates` | Occupancy, vulnerable groups, supplies, and services. |
| `incidents` | Operational incidents. |
| `incident_history` | Incident status, priority, resource, and administrative timeline. |
| `response_resources` | Teams, vehicles, and equipment readiness. |
| `incident_resource_assignments` | Resource dispatch and release records. |
| `cross_barangay_evacuation_allocations` | Occupant attribution to non-host barangays. |
| `report_snapshots` | Immutable SitRep payloads and hashes. |
| `system_audit_log` | Immutable trigger-generated before/after audit records. |
| `app_users` | Authorized OIDC emails, roles, and active status. |

### 10.4 Immutability and history

PostgreSQL triggers prevent updates or deletes to report snapshots and system
audit records. Event, validation, incident, resource, and correction workflows
also preserve their own operational history and actor snapshots.

## 11. Local installation and configuration

### 11.1 Prerequisites

- Windows development or approved server environment;
- Python 3.14;
- PostgreSQL server;
- PostgreSQL client tools including `pg_dump` and `pg_restore` for backups;
- a Google OIDC client;
- Git for source control and preflight checks.

### 11.2 Install

Run from the repository root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Set the protected local values:

```dotenv
DATABASE_URL=postgresql+psycopg://APPLICATION_USER:APPLICATION_PASSWORD@localhost:5432/mdrrmo_dashboard
APP_DEPLOYMENT_MODE=local
APP_TIMEZONE=Asia/Manila
```

`APP_TIMEZONE` is retained in the environment template for deployment clarity,
but the current application code explicitly renders operational timestamps in
Asia/Manila. Changing that variable alone does not currently change display
behavior.

Populate `.streamlit/secrets.toml` without committing it:

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "REPLACE_WITH_A_LONG_RANDOM_SECRET"
client_id = "REPLACE_WITH_GOOGLE_CLIENT_ID"
client_secret = "REPLACE_WITH_GOOGLE_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

Apply and seed the database:

```powershell
alembic upgrade head
python -m scripts.seed_master_data
python -m scripts.create_app_user --email "ADMIN_EMAIL" --name "Administrator" --role "Administrator"
```

Verify and start:

```powershell
python -m scripts.test_database
python -m scripts.verify_database
python -m unittest discover -s tests -v
python -m scripts.deployment_preflight
python -m streamlit run app.py
```

Use module invocation for deployment preflight. Directly running
`scripts/deployment_preflight.py` can fail to resolve the repository's `config`
package, depending on the Python path.

### 11.3 Protected and generated files

Do not commit:

- `.env`;
- `.streamlit/secrets.toml`;
- populated production environment files;
- logs, exports, backup archives, checksums, or backup metadata;
- recovery passwords or service-account recovery codes;
- machine-specific performance results.

## 12. Cloud-pilot configuration

### 12.1 Required protected settings

Use `.streamlit/secrets.cloud.example.toml` only as a template. Populate values
in the deployment platform's protected secrets editor.

| Setting | Purpose | Default or boundary |
|---|---|---|
| `APP_DEPLOYMENT_MODE` | Enables cloud safeguards | Must be `cloud` |
| `DATABASE_URL` | Remote PostgreSQL connection | Must contain a real remote host |
| `DB_SSLMODE` | PostgreSQL TLS policy | `require`; `verify-ca` and `verify-full` allowed |
| `DB_POOL_SIZE` | Persistent pool size | Default 4; allowed 1–8 |
| `DB_MAX_OVERFLOW` | Temporary overflow connections | Default 1; allowed 0–4 |
| `DB_POOL_TIMEOUT_SECONDS` | Wait for a pool connection | Default 5; allowed 1–10 |
| `DB_POOL_RECYCLE_SECONDS` | Recycle aged connections | Default 300; allowed 60–3600 |
| `DB_CONNECT_TIMEOUT_SECONDS` | PostgreSQL connection timeout | Default 5; allowed 1–30 |
| `CLOUD_DATABASE_CONNECTION_LIMIT` | Health-check budget | Default 20 |
| `CLOUD_DATABASE_STORAGE_LIMIT_MB` | Health-check storage budget | Default 1024 MB |

Cloud mode rejects insecure PostgreSQL SSL modes such as `disable`, `allow`,
or `prefer`.

### 12.2 OIDC callback

For an application base URL such as:

```text
https://mdrrmo-naic-pilot.streamlit.app
```

the callback must be exactly:

```text
https://mdrrmo-naic-pilot.streamlit.app/oauth2callback
```

The same value must be present in Streamlit secrets and registered with Google.

### 12.3 Pilot safety rules

- Begin with an empty database and clearly marked disposable test data.
- Do not copy existing records until management classifies and approves them.
- Restrict access to approved pilot users.
- Test all six roles, hibernation/wake behavior, multiple sessions, and exports.
- Do not operate simultaneous local and cloud writers.
- Freeze writes and create a verified archive before an approved cutover.
- Stop the pilot if credentials are exposed, access is unauthorized, records
  diverge unexpectedly, or the owner loses control of a service account.

Run cloud preflight:

```powershell
python -m scripts.cloud_pilot_preflight
python -m scripts.cloud_pilot_preflight --secrets-file "PATH_TO_PROTECTED_SECRETS"
```

The first command validates repository safety and reports manual secret checks.
The second can validate a protected populated file; never commit that file.

## 13. Administration and maintenance

### 13.1 Routine administrator checks

At the start of an operational period:

1. Confirm System Health has no FAIL result.
2. Confirm at least one active Administrator exists.
3. Confirm the database revision matches the code.
4. Confirm required immutability triggers are installed.
5. Confirm the active event is correct.
6. Confirm recent backup and off-machine retention evidence.
7. Review audit activity and application logs for unexplained errors.

### 13.2 Useful commands

```powershell
# Database connectivity and master data
python -m scripts.test_database
python -m scripts.verify_database

# Migrations
alembic current
alembic heads
alembic upgrade head

# Tests
python -m unittest discover -s tests -v

# Deployment-candidate readiness
python -m scripts.deployment_preflight

# Use a different backup age gate
python -m scripts.deployment_preflight --backup-max-age-hours 48

# Cloud pilot
python -m scripts.cloud_pilot_preflight

# Read-only dashboard diagnostic
python -m scripts.test_dashboard_summary

# Performance baseline
python -m scripts.phase10_performance_baseline
```

### 13.3 First or emergency Administrator account

The command-line user tool creates an account or reactivates/updates an existing
email:

```powershell
python -m scripts.create_app_user `
  --email "ADMIN_EMAIL" `
  --name "Administrator Name" `
  --role "Administrator"
```

Restrict terminal and database access because this command is an administrative
bootstrap path.

### 13.4 Logs

Application errors are written to ignored rotating files under:

```text
logs/mdrrmo_app.log
```

User-visible error references can be matched to log entries. Logging utilities
redact known database URLs, passwords, secrets, tokens, and bearer credentials.
Do not assume redaction makes arbitrary sensitive text safe to log.

## 14. Backup and recovery

### 14.1 Backup set

A successful backup creates:

- a PostgreSQL custom-format `.backup` archive;
- a `.json` metadata file containing creation time, database name, Alembic
  revision, SHA-256, file size, table counts, and verification state;
- a `.sha256` checksum file.

Keep all three files together.

### 14.2 Create and verify

```powershell
python -m scripts.backup_database
python -m scripts.backup_database --directory "APPROVED_ENCRYPTED_FOLDER"
python -m scripts.verify_backup "backups\BACKUP_NAME.backup"
```

The service searches `PATH` and common Windows PostgreSQL installation folders
for `pg_dump` and `pg_restore`.

Archive verification checks:

- file existence and optional checksum;
- `pg_restore --list` readability;
- presence of core database objects.

Archive readability is necessary but is not proof that a complete restore will
succeed. Perform restore drills.

### 14.3 Dedicated maintenance role

The normal application role must remain least privilege and must not receive
`CREATEDB`. Create a separate restore-maintenance role:

```powershell
python -m scripts.setup_restore_maintenance_role
```

Passwords are prompted securely and must not be passed as command-line
arguments, stored in `.env`, committed, or left in shell history.

### 14.4 Restore testing

Use a disposable test or UAT database, never the configured operational
database:

```powershell
python -m scripts.restore_test --latest
python -m scripts.phase8_validation
```

The complete Phase 8 validation:

1. creates and verifies a backup;
2. creates a disposable restore database;
3. restores as the normal application role;
4. verifies revision, counts, schema, and triggers;
5. creates a second empty disposable database;
6. migrates from zero to head;
7. verifies parity and immutability;
8. removes the disposable databases;
9. writes non-secret evidence.

For a fresh-database migration drill:

```powershell
python -m scripts.fresh_database_test `
  --database-url "postgresql+psycopg://USER:PASSWORD@HOST:5432/mdrrmo_uat_test"
```

The target name must contain `test` or `uat`, must be empty, and must not be the
configured production database.

### 14.5 Cloud recovery

Cloud recovery has two required layers:

1. **Provider-managed recovery:** an authorized custodian verifies the Aiven
   recovery state in its console and records evidence.
2. **Independent encrypted archive:** a trusted workstation creates and stores
   a complete backup set outside Aiven and Streamlit.

The application cannot independently prove provider-managed backup status.
Restore cloud archives only into isolated local or staging PostgreSQL targets.

## 15. Security, privacy, and auditing

### 15.1 Authentication and authorization

- Google OIDC authenticates identity.
- PostgreSQL `app_users` records authorize application access.
- Authorization is refreshed from PostgreSQL on each Streamlit rerun.
- Pages also enforce permissions before rendering.
- Service functions recheck the actor and permission before writes.

### 15.2 Least privilege

- Give users the least-powerful appropriate role.
- Keep the normal database application role without `CREATEDB`.
- Use separate maintenance credentials for restore/database-lifecycle work.
- Keep database access unavailable to general office clients.
- Require HTTPS for any non-local deployment.

### 15.3 Secret handling

Never place the following in Git, screenshots, tickets, chat, ordinary email,
or public links:

- database URLs and passwords;
- OAuth client secrets and cookie secrets;
- recovery codes or maintenance passwords;
- backup archives containing operational or personal data;
- private certificate material.

If a credential is exposed, stop affected access, rotate/revoke the credential,
review audit and provider logs, and document the incident.

### 15.4 Database auditing

Database triggers audit INSERT, UPDATE, and DELETE operations on event,
reporting, evacuation, incident, resource, user, and snapshot tables. Records
include table, operation, record ID, actor snapshot where available, old data,
new data, and time.

The audit table itself is append-only. Administrative database access should
still be limited because privileged database owners may operate outside normal
application controls.

### 15.5 Privacy

Operational records may include identities, locations, vulnerable-group counts,
medical-case counts, and incident details. Use only approved data, minimize
unnecessary personal information, restrict access, and follow applicable LGU
privacy and records-management rules.

## 16. Errors and troubleshooting

### 16.1 User-facing problems

| Message or symptom | Likely cause | Correct response |
|---|---|---|
| Google sign-in succeeds but access is denied | Email has no authorized application account | Ask an Administrator to authorize the exact OIDC email. |
| “Your system account is inactive” | Administrator deactivated the account | Confirm authorization with the system custodian. |
| Invalid role assignment | Stored role is not one of the six supported roles | Administrator must correct the database-backed role. |
| Authentication expired | OIDC token reached its expiry time | Sign in again. |
| No pages are visible | Role has no recognized permissions | Correct the user's role; do not bypass page guards. |
| No active disaster event | Event was not created, was closed, or changed during the operation | Confirm Event Control before resubmitting. |
| More than one active event | Database integrity violation | Stop writes and have an Administrator/database custodian investigate. |
| Duplicate submission ignored | The same form-generation token was already saved | Refresh the relevant list and confirm the existing record. Do not repeatedly submit. |
| Report already reviewed | Another validator completed the review | Refresh the queue and inspect current status. |
| Correction instructions required | Needs Correction was selected without notes | Enter specific actionable correction instructions. |
| Population figures rejected | Family/individual or displaced/affected mathematics is impossible | Recheck source totals; do not alter figures merely to pass validation. |
| No Flooding with non-zero depth | Flood status and depth conflict | Correct the status or verified depth. |
| Center status rejected | Standby/Closed has occupants, or capacity/status rules conflict | Correct occupancy/status using verified source data. |
| Cross-barangay allocation rejected | Origin, occupancy, or allocated totals conflict | Review the current center report and all allocations. |
| Incident cannot move backward | Normal lifecycle is forward-only | Use the controlled reopen workflow only when authorized and justified. |
| Resource cannot be assigned | Resource is unavailable/already assigned, or incident is closed | Review resource and incident state; release old assignment if appropriate. |
| Snapshot generation rejected | Event changed, mode is invalid, or duplicate token was used | Refresh event context and regenerate deliberately. |
| Snapshot integrity failure | Stored JSON no longer matches its SHA-256 hash | Do not export or issue it; investigate database integrity and audit history. |
| Generic error with reference | Unexpected exception was logged safely | Give the reference and time to the Administrator; do not paste secrets. |

### 16.2 Installation and database problems

| Problem | Diagnosis and resolution |
|---|---|
| `DATABASE_URL is missing` | Create the protected `.env` or deployment secret and restart the app. |
| PostgreSQL connection refused/timed out | Verify service state, host, port, firewall, credentials, TLS policy, and network route. |
| `ModuleNotFoundError: config` during preflight | Run from repository root with `python -m scripts.deployment_preflight`. |
| Alembic database revision differs from code | Stop normal writes, review pending migrations, back up, and run the approved migration procedure. |
| Required table or trigger missing | Treat as FAIL; restore/migrate only under the deployment runbook. |
| `pg_dump` or `pg_restore` not found | Install PostgreSQL client tools or add the PostgreSQL `bin` directory to PATH. |
| Backup checksum mismatch | Do not use the archive; locate a verified copy and investigate corruption or replacement. |
| Archive readable but expected objects are missing | Do not accept it as a complete system backup. Create or locate a correct archive. |
| Backup directory is not writable | Correct filesystem permissions or select an approved writable destination. |
| Cloud SSL mode rejected | Set `DB_SSLMODE` to `require`, `verify-ca`, or `verify-full`. |
| Cloud connection budget warning | Reduce sessions/pool settings or upgrade the approved database plan before capacity is exhausted. |
| Cloud storage budget warning | Review data growth, retention, archiving, and approved service capacity. |

### 16.3 Streamlit-specific behavior

- Streamlit reruns the page after interactions. Form state is intentionally
  stored in Session State.
- During development, a partial Streamlit reload can retain an older imported
  module. A newly added shared UI function may appear missing until the guarded
  reload runs or Streamlit is fully restarted.
- If UI behavior is inconsistent immediately after code changes, perform a full
  Streamlit restart before diagnosing database data.
- Cloud applications may hibernate. Test and communicate the accepted wake-up
  delay for the pilot.

### 16.4 Failure-response rules

- Do not bypass authorization or validation to clear an error.
- Do not edit immutable snapshots or audit rows directly.
- Do not retry a failed write blindly; first confirm whether it committed.
- Preserve the error time, page, action, user, and reference.
- Keep secrets and full database URLs out of screenshots and support messages.
- Escalate multiple-active-event, missing-trigger, hash-mismatch, unauthorized
  access, credential exposure, and unexpected data-divergence incidents
  immediately.

## 17. Known limitations and unresolved decisions

### 17.1 Production limitations

- Automated checks cannot approve authoritative master data, alert definitions,
  legal/privacy requirements, network security, or office procedures.
- The official Excel and PDF layouts remain provisional until MDRRMO supplies
  and approves authoritative templates.
- Local backups remain on the application machine until copied to approved
  independent storage.
- Streamlit Community Cloud storage is temporary and must not be treated as
  backup storage.
- Provider-managed cloud recovery cannot be independently verified by the app.
- Internet-dependent cloud deployment needs an approved outage fallback.

### 17.2 Operational limitations

- The dashboard presents reported source data; it cannot determine whether a
  field report is factually true without human verification.
- Reconciliation identifies differences but does not decide which source is
  correct.
- Official Validated mode can be older than provisional mode because it excludes
  newer reports that have not completed validation.
- A zero or unknown value must be interpreted with its source and report time;
  it may not mean the hazard is absent.
- Incident/resource status supports coordination but does not replace radio,
  dispatch, medical, or command protocols.

### 17.3 Code and release-state cautions

- This document reflects a working tree with uncommitted Phase 11D and UI
  refactoring changes. Run the complete regression, migration, preflight,
  backup, and recovery checks before tagging or deploying a release.
- Some older documentation, particularly the README development-status section,
  no longer reflects all implemented capabilities. This handbook and current
  code should be reconciled into future release documentation.
- Performance results under `performance_results/` are machine-specific
  snapshots, not permanent service-level guarantees.

## 18. Release and operational checklists

### 18.1 Before each deployment

- [ ] Working tree and intended commit reviewed.
- [ ] No secret, backup, export, log, or populated production file tracked.
- [ ] Dependencies installed from the pinned requirements.
- [ ] Full unit/contract suite passes.
- [ ] Alembic head is singular and database revision matches it.
- [ ] System Health has no FAIL result.
- [ ] Snapshot and audit immutability triggers are present.
- [ ] A recent verified backup exists.
- [ ] Restore evidence remains valid for the intended release.
- [ ] Role-by-role access is tested.
- [ ] OIDC callback exactly matches the deployed HTTPS URL.
- [ ] Manual production or pilot gates are signed by authorized people.

### 18.2 Before each operational use

- [ ] Correct active event, classification, alert, EOC, and SitRep confirmed.
- [ ] Authorized users and roles reviewed.
- [ ] Encoder and validator separation assigned where staffing allows.
- [ ] Source-report and communication procedures confirmed.
- [ ] Dashboard freshness and warnings reviewed.
- [ ] Backup location and custodian confirmed.
- [ ] Outage/fallback procedure available.

### 18.3 Before issuing an official report

- [ ] Official Validated mode selected.
- [ ] Pending validation and Needs Correction workload reviewed.
- [ ] Reconciliation differences investigated and documented.
- [ ] Event and SitRep context verified.
- [ ] Snapshot ID and SHA-256 recorded.
- [ ] Export opened and visually reviewed.
- [ ] Issued copy preserved according to office records policy.

## 19. Repository map

```text
app.py                         Streamlit entry point and role-filtered navigation
config/                        Access policy, operational constants, runtime profile
database/                      Connection, SQLAlchemy models, queries, migrations
pages/                         User-facing Streamlit workspaces
services/                      Business rules, authorization, validation, transactions
utils/                         UI, auth, formatting, logging, view contracts, caches
scripts/                       Setup, verification, backup, recovery, performance tools
styles/                        Shared CSS design system
assets/                        Branding images
tests/                         Unit, regression, reliability, and contract tests
deployment/                    Runbooks, UAT, architecture, pilot decision records
design/                        Visual identity and operational-console guidance
performance/                   Performance rules and measurement plan
backups/                       Ignored local database archives
exports/                       Ignored generated exports
logs/                          Ignored rotating application log
requirements.txt               Pinned Python dependencies
alembic.ini                    Migration configuration
SYSTEM_DOCUMENTATION.md        Consolidated handbook
```

Specialized references:

- `deployment/DEPLOYMENT_RUNBOOK.md`
- `deployment/PRODUCTION_ARCHITECTURE.md`
- `deployment/UAT_CHECKLIST.md`
- `deployment/UAT_SIGNOFF.md`
- `deployment/CLOUD_PILOT_RUNBOOK.md`
- `deployment/CLOUD_PILOT_DECISION_CHECKLIST.md`
- `performance/PERFORMANCE_PLAN.md`
- `design/VISUAL_IDENTITY.md`
- `design/OPERATIONAL_CONSOLE.md`

## 20. Glossary

| Term | Meaning |
|---|---|
| Affected | Reported as impacted by the disaster; not necessarily evacuated, injured, or homeless. |
| Alert level | WHITE, BLUE, or RED operational alert master value; official meaning requires MDRRMO approval. |
| BDRRMC | Barangay Disaster Risk Reduction and Management Committee. |
| EOC | Emergency Operations Center. |
| Inside EC | Recorded inside a formal evacuation center. |
| Outside EC | Displaced but recorded outside a formal evacuation center. |
| OIDC | OpenID Connect; the external identity protocol used for Google sign-in. |
| PSGC | Philippine Standard Geographic Code. |
| Provisional | Current usable operational information that may not be fully validated. |
| Reconciliation | Comparison of independently reported barangay and evacuation-center figures. |
| SitRep | Situation Report. |
| Snapshot | Immutable stored copy of the selected reporting view at a specific time. |
| Superseded | Retained previous report replaced by a corrected resubmission. |
| UAT | User Acceptance Testing. |
| Validator | Authorized user who accepts a report or returns it with correction instructions. |

---

For operational support, record the date/time, user, page, action, visible
message, and error reference. Do not include passwords, database URLs, OAuth
secrets, recovery codes, or confidential records in ordinary support messages.
