# Phase 11D Cloud Pilot Runbook

This runbook prepares a controlled Streamlit Community Cloud and Aiven
PostgreSQL pilot. It does not authorize production use or the transfer of
official operational records.

## Safety boundary

- Phase 11C7 remains the verified local rollback baseline.
- Use the `phase/11d-cloud-pilot` branch for cloud-readiness work.
- Treat the existing database as UAT/test data until management classifies it.
- Do not commit `.env`, `.streamlit/secrets.toml`, database URLs, passwords,
  OAuth secrets, backup archives, or recovery codes.
- Do not restore over the live local or cloud operational database.
- Do not use Streamlit application storage as backup storage.

## Deployment profiles

### Local profile

`APP_DEPLOYMENT_MODE=local` is the default. The verified Phase 11C7 local
backup, archive inspection, and controlled restore guidance remain available.

### Cloud profile

`APP_DEPLOYMENT_MODE=cloud` enables:

- required PostgreSQL transport encryption;
- a small bounded SQLAlchemy connection pool;
- connection and storage budget checks;
- cloud-aware System Health messaging;
- removal of local backup creation from the Streamlit user interface;
- separate Aiven recovery and independent-archive guidance.

## Management decisions required before provisioning

Record these decisions in `deployment/CLOUD_PILOT_DECISION_CHECKLIST.md`.

- official office-controlled owner account;
- approved Streamlit application address;
- approved pilot users and roles;
- classification of existing records as test, official, or mixed;
- approved independent encrypted backup destination;
- privacy and third-party cloud approval;
- named primary and backup system custodians.

## Aiven staging procedure

1. Create one empty free PostgreSQL service using the approved owner account.
2. Keep the service URI, password, and certificate material private.
3. Record the service region because free-tier placement may not be selectable.
4. Configure an administrator workstation with the protected `DATABASE_URL`.
5. Apply the current schema with `alembic upgrade head`.
6. Create only approved pilot accounts.
7. Load disposable UAT data first; do not import the current database blindly.
8. Run schema, trigger, audit, role, connection, and storage checks.

## Streamlit staging procedure

1. Connect the private GitHub repository to Streamlit Community Cloud.
2. Deploy the cloud-pilot branch to a temporary pilot address.
3. In Advanced settings, select Python 3.14 to match the verified project
   environment. Changing the Python version later may require a new deployment.
4. Copy `.streamlit/secrets.cloud.example.toml` into the protected Streamlit
   secrets editor and replace every placeholder there, not in the repository.
5. Register the exact HTTPS `/oauth2callback` URL in Google OAuth.
6. Keep the deployment private or restricted to the approved pilot group.
7. Test every application role and every permitted page.
8. Test hibernation/wake behavior and multiple simultaneous sessions.

## Recovery layers

### Layer 1: Aiven-managed recovery

An authorized custodian verifies recovery status in the Aiven Console and
records the date and result in the office backup register. The Streamlit app
cannot independently prove this provider-controlled state.

### Layer 2: independent encrypted archive

From a trusted workstation with PostgreSQL client tools and protected Aiven
credentials, create the archive in an approved encrypted destination:

```powershell
python scripts/backup_database.py --directory "<APPROVED_ENCRYPTED_BACKUP_FOLDER>"
```

Keep the `.backup`, `.json`, and `.sha256` files together. Never use GitHub,
public links, ordinary email, or Streamlit storage as the archive destination.

## Restore drill

Restore only to a disposable local or staging PostgreSQL server. Never use the
live Aiven pilot database as the restore target. Verify:

- SHA-256 checksum;
- archive readability;
- Alembic revision;
- required tables and immutable audit triggers;
- expected table counts;
- successful cleanup of the disposable target.

## Pilot acceptance gates

- No secret or backup artifact is tracked by Git.
- The cloud database uses TLS.
- The database revision matches the code head.
- Required audit and snapshot immutability triggers are present.
- All six roles pass authorized and unauthorized access tests.
- Peak database connections remain below 75% of the configured limit.
- Database size remains below 75% of the configured storage budget.
- One independent archive has been successfully restored in isolation.
- Sleep/wake behavior and exports are acceptable.
- Management has approved the pilot users, data scope, and fallback procedure.

## Rollback rule

Do not use simultaneous local and cloud writes. Before an approved cutover,
freeze writes and create a final verified archive. If the pilot fails, stop
cloud writes, preserve cloud-only records for reconciliation, and return to the
verified local deployment under the approved maintenance procedure.
