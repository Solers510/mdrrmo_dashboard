# MDRRMO Naic Operations Dashboard

A Streamlit + PostgreSQL disaster-response operations dashboard for MDRRMO Naic.

## Current capabilities

- Google OIDC sign-in through Streamlit authentication
- PostgreSQL-backed application authorization and role-based access
- Active disaster-event control
- Barangay situation reporting
- Barangay report validation with authenticated reviewer identity
- Evacuation-center master records and occupancy updates
- Operational and validated dashboard views
- User administration

## Project structure

```text
app.py                    Streamlit entry point and role-based navigation
config/                   Constants and access-control policy
database/                 SQLAlchemy models, repositories, and Alembic migrations
pages/                    Streamlit application pages
services/                 Business logic and validation
scripts/                  Setup, verification, and maintenance scripts
utils/                    Shared application utilities
```

## Local setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and configure `DATABASE_URL`.
4. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and configure local OIDC credentials.
5. Apply migrations:

```powershell
alembic upgrade head
```

6. Seed master data:

```powershell
python -m scripts.seed_master_data
```

7. Create the first authorized application user:

```powershell
python -m scripts.create_app_user --email "YOUR_LOGIN_EMAIL" --name "Administrator" --role "Administrator"
```

8. Run the application:

```powershell
python -m streamlit run app.py
```

## Security

Do not commit `.env` or `.streamlit/secrets.toml`. Both are intentionally ignored by Git. Example files contain placeholders only.

Authentication identifies the Google/OIDC user. Authorization is separately enforced through PostgreSQL `app_users` records and role permissions.

## Development status

The system is still under active development. Incident persistence, event closure and alert transitions, unified validation, exports, backups, production hardening, and final MDRRMO user-acceptance testing remain incomplete.

Before production use, complete backup/restore testing, production-safe error handling, deployment security, audit logging, and formal operational testing.
