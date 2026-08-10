# MDRRMO Naic User Acceptance Test Checklist

Use dedicated test accounts for each role. Do not change a real user's role
back and forth during a disaster operation.

Record **PASS**, **FAIL**, or **N/A** and notes for every item.

## 1. Authentication and session

- [ ] Authorized account can sign in with Google.
- [ ] Unauthorized Google account is rejected.
- [ ] Inactive application account is rejected.
- [ ] Sign out works.
- [ ] Expired authentication requires sign-in again.

## 2. Viewer

- [ ] Can open Dashboard.
- [ ] Cannot access Event Control.
- [ ] Cannot submit Barangay reports.
- [ ] Cannot submit EC reports.
- [ ] Cannot validate reports.
- [ ] Cannot access Reports.
- [ ] Cannot access Administration.

## 3. Executive

- [ ] Can open Dashboard.
- [ ] Can open saved Reports/SitReps.
- [ ] Cannot submit or validate operational reports.
- [ ] Cannot manage events, incidents, EC master records, or users.

## 4. Encoder

- [ ] Can open Dashboard.
- [ ] Can submit a Barangay report.
- [ ] Double-click/repeat submission does not create an accidental duplicate.
- [ ] Invalid population mathematics is blocked.
- [ ] Can submit EC occupancy updates.
- [ ] Cannot create EC master records.
- [ ] Cannot validate reports.
- [ ] Cannot manage users.

## 5. Validator

- [ ] Can open Dashboard.
- [ ] Can open Report Validation.
- [ ] Can validate a submitted Barangay report.
- [ ] Can return a report as Needs Correction with required instructions.
- [ ] Correction/resubmission preserves prior history.
- [ ] Can validate EC reports.
- [ ] Can review reconciliation warnings.
- [ ] Cannot submit operational reports.
- [ ] Cannot manage users.

## 6. Operations Officer

- [ ] Can manage active event lifecycle.
- [ ] Can change event classification/alert/EOC/SitRep metadata.
- [ ] Can submit Barangay and EC reports.
- [ ] Can validate reports.
- [ ] Can manage EC master records.
- [ ] Can access incident/response operations.
- [ ] Can generate reports.
- [ ] Cannot access User Administration/System Health administration.

## 7. Administrator

- [ ] Has all application pages.
- [ ] Can add an authorized application user.
- [ ] Can change another user's role/status.
- [ ] Cannot accidentally remove the final active Administrator.
- [ ] System Health page loads with zero FAIL checks.
- [ ] Audit Log opens.
- [ ] Backup & Restore lists verified backups.

## 8. Event lifecycle

- [ ] Exactly one active event can be used operationally.
- [ ] Same storm/event name may keep evolving classification.
- [ ] Event can be closed/stood down.
- [ ] Closed event no longer accepts normal new operational reports.
- [ ] Administrator reopen requires the intended controlled workflow.
- [ ] Event change history is preserved.

## 9. Barangay data integrity

- [ ] Families cannot exceed individuals.
- [ ] Inside-EC families cannot exceed Inside-EC individuals.
- [ ] Outside-EC families cannot exceed Outside-EC individuals.
- [ ] Total displaced cannot exceed affected.
- [ ] Affected but not displaced cannot become mathematically impossible.
- [ ] No-flooding status requires zero flood depth.
- [ ] Failed validation does not clear the user's form unexpectedly.

## 10. Evacuation centers

- [ ] Occupancy cannot contain negative counts.
- [ ] Closed center requires zero occupants.
- [ ] Over-capacity occupancy requires appropriate status.
- [ ] Food/water/electricity/sanitation fields persist correctly.
- [ ] Vulnerable groups persist correctly.
- [ ] Barangay-vs-EC mismatch is a warning/reconciliation issue rather than
      silent data replacement.

## 11. Reporting

- [ ] Provisional Operational snapshot can be generated.
- [ ] Official Validated snapshot uses validated source reports.
- [ ] Snapshot cannot be edited/deleted through normal application workflow.
- [ ] Excel export opens.
- [ ] Excel contains all expected sheets.
- [ ] PDF SitRep opens.
- [ ] Historical snapshot can be downloaded again.
- [ ] Snapshot hash remains stable.

## 12. Audit

- [ ] A real post-install administrative/operational change appears in Audit Log.
- [ ] Audit record shows table, operation, record ID, time and actor when available.
- [ ] Previous/new row state can be inspected.
- [ ] Application has no audit edit/delete control.

## 13. Backup and recovery

- [ ] `python scripts/backup_database.py` succeeds.
- [ ] Backup SHA-256 is produced.
- [ ] `pg_restore --list` verification succeeds.
- [ ] Backup metadata records Alembic revision and table counts.
- [ ] Backup is copied to an off-machine/off-site location.
- [ ] Full restore drill succeeds using a disposable database and a dedicated
      maintenance role.
- [ ] Restored table counts and Alembic revision match the backup metadata.

## 14. Failure behavior

- [ ] Database outage produces a user-safe error rather than a raw traceback.
- [ ] After database recovery the application reconnects.
- [ ] No secret/password appears in user-visible errors.
- [ ] Application log is created under ignored `logs/`.
- [ ] A failed submission is rolled back and does not create a partial record.

## 15. Production environment

- [ ] Authoritative 30-barangay master list verified by MDRRMO/LGU.
- [ ] PSGC codes verified.
- [ ] Alert-level definitions verified.
- [ ] Final HTTPS hostname available.
- [ ] TLS certificate verified.
- [ ] Google OIDC production redirect URI registered.
- [ ] `.env` not committed.
- [ ] `.streamlit/secrets.toml` not committed.
- [ ] Backups and logs not committed.

## Acceptance

Prototype/UAT accepted by:

- Name:
- Role:
- Date:
- Result:
- Remaining issues:
