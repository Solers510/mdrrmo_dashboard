# MDRRMO Naic Prototype Deployment Runbook

## Purpose

This runbook is for the stable prototype/deployment-candidate stage. It is
not authorization for production use by itself.

## Current deployment principles

1. Use a dedicated PostgreSQL application role with least privilege.
2. Do not grant `CREATEDB` to the normal application role.
3. Keep `.env` and `.streamlit/secrets.toml` outside Git.
4. Use HTTPS for any non-local deployment.
5. Replace the localhost Google OIDC redirect URI with the final HTTPS
   callback URI before production.
6. Maintain verified PostgreSQL backups outside the application machine.
7. Complete the role-by-role UAT checklist before production.

## Supported development baseline

- Windows
- PyCharm
- Python 3.14
- PostgreSQL
- Streamlit
- Dependencies pinned in `requirements.txt`

## Fresh installation

1. Clone the repository.
2. Create a Python 3.14 virtual environment.
3. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env`.
5. Set `DATABASE_URL` in `.env`.
6. Copy `.streamlit/secrets.toml.example` to
   `.streamlit/secrets.toml`.
7. Fill the Google OIDC values without committing them.
8. Run:

   ```powershell
   alembic upgrade head
   python -m unittest discover -s tests -v
   python scripts/deployment_preflight.py
   ```

9. Start:

   ```powershell
   python -m streamlit run app.py
   ```

## Production gates that cannot be automated completely

- authoritative barangay master list verified by MDRRMO/LGU;
- alert-level terminology/meaning verified by MDRRMO;
- full backup restore performed with a dedicated maintenance account;
- production hostname and TLS verified;
- Google OIDC redirect updated and registered;
- role-by-role UAT completed and signed off.

## Fresh-database migration drill

Create an **empty disposable PostgreSQL database** whose name contains
`test` or `uat`, then run:

```powershell
python scripts/fresh_database_test.py --database-url "postgresql+psycopg://USER:PASSWORD@HOST:5432/mdrrmo_uat_test"
```

The script refuses the configured production database and refuses a
non-empty target database. It leaves the test database in place so it can
be inspected and later dropped using a maintenance account.

## Backups

Create a verified backup:

```powershell
python scripts/backup_database.py
```

Verify an archive:

```powershell
python scripts/verify_backup.py backups\<backup-name>.backup
```

## Phase 8 recovery validation

The normal application role must remain least privilege and must **not**
receive `CREATEDB`.

Create or reset the dedicated restore-maintenance role. Passwords are
requested securely and are not accepted as command-line arguments:

```powershell
python scripts/setup_restore_maintenance_role.py
```

Then run the complete validation:

```powershell
python scripts/phase8_validation.py
```

This command:

1. creates and verifies a new PostgreSQL backup;
2. creates a disposable restore database with the maintenance role;
3. restores the archive **as the normal application role**;
4. verifies the Alembic revision and every recorded table row count;
5. compares the restored table/trigger schema with the source database;
6. creates another empty disposable database;
7. runs Alembic from zero to head as the application role;
8. verifies table/trigger parity and immutability triggers;
9. drops both disposable databases; and
10. writes non-secret evidence to
   `deployment/PHASE8_VALIDATION_RESULTS.json`.

Do not place the maintenance password in `.env`, Git, shell history, or the
application's normal `DATABASE_URL`.

## Release rule

A prototype can be considered functionally stable when automated preflight
has zero FAIL results and the UAT checklist is complete. Production use
still requires the manual production gates listed above.
