param(
    [switch]$SkipCommit
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Need([string]$Path) {
    if (-not (Test-Path $Path)) {
        throw "Required file is missing: $Path"
    }
}

function NeedText(
    [string]$Path,
    [string]$Pattern,
    [string]$Description
) {
    if (-not (Select-String -Path $Path -Pattern $Pattern -Quiet)) {
        throw "Prerequisite missing: $Description`nFile: $Path"
    }
}

Step "Checking Phase 13B prerequisites"

Need "app.py"
Need "config\access_control.py"
Need "database\models.py"
Need "database\repositories.py"
Need "services\user_admin_service.py"
Need "services\validation_service.py"
Need "pages\user_admin.py"
Need "pages\validation.py"
Need "utils\auth.py"
Need ".streamlit\secrets.toml"

NeedText "config\access_control.py" "PERMISSION_MANAGE_USERS" "PERMISSION_MANAGE_USERS must exist."
NeedText "database\models.py" "reviewed_by_user_id" "BarangayUpdate.reviewed_by_user_id must already be added."
NeedText "services\validation_service.py" "reviewer_user_id" "Validation service must use authenticated reviewer_user_id."
NeedText "pages\validation.py" "current_user" "Validation page must use the authenticated user."

Write-Host "Prerequisites: OK" -ForegroundColor Green

Step "Checking OAuth secret Git safety"

git check-ignore .streamlit/secrets.toml | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw ".streamlit/secrets.toml is not ignored by Git."
}

if (git ls-files .streamlit/secrets.toml) {
    throw ".streamlit/secrets.toml is already tracked by Git."
}

Write-Host "Secrets safety: OK" -ForegroundColor Green

Step "Backing up and replacing app.py"

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item app.py "app.py.phase13b-backup-$stamp"

$appContent = @'
import streamlit as st

from config.access_control import (
    PERMISSION_MANAGE_EVENTS,
    PERMISSION_MANAGE_EVACUATION_CENTERS,
    PERMISSION_MANAGE_INCIDENTS,
    PERMISSION_MANAGE_USERS,
    PERMISSION_SUBMIT_BARANGAY_UPDATES,
    PERMISSION_SUBMIT_EVACUATION_UPDATES,
    PERMISSION_VALIDATE_BARANGAY_REPORTS,
    PERMISSION_VIEW_DASHBOARD,
    PERMISSION_VIEW_REPORTS,
)
from utils.auth import (
    get_current_app_user,
    has_any_permission,
    has_permission,
    login_screen,
    render_account_sidebar,
)


st.set_page_config(
    page_title="MDRRMO Naic Dashboard",
    layout="wide",
)


if not getattr(st.user, "is_logged_in", False):
    login_screen()


current_user = get_current_app_user()
render_account_sidebar(current_user)


dashboard_page = st.Page(
    "pages/dashboard.py",
    title="Dashboard",
    default=True,
)
event_control_page = st.Page(
    "pages/event_control.py",
    title="Event Control",
)
barangay_updates_page = st.Page(
    "pages/barangay_updates.py",
    title="Barangay Updates",
)
validation_page = st.Page(
    "pages/validation.py",
    title="Report Validation",
)
evacuation_centers_page = st.Page(
    "pages/evacuation_centers.py",
    title="Evacuation Centers",
)
incidents_page = st.Page(
    "pages/incidents.py",
    title="Incidents",
)
reports_page = st.Page(
    "pages/reports.py",
    title="Reports",
)
user_admin_page = st.Page(
    "pages/user_admin.py",
    title="User Administration",
)


operations_pages = []

if has_permission(current_user, PERMISSION_VIEW_DASHBOARD):
    operations_pages.append(dashboard_page)

if has_permission(current_user, PERMISSION_MANAGE_EVENTS):
    operations_pages.append(event_control_page)

if has_permission(
    current_user,
    PERMISSION_SUBMIT_BARANGAY_UPDATES,
):
    operations_pages.append(barangay_updates_page)

if has_permission(
    current_user,
    PERMISSION_VALIDATE_BARANGAY_REPORTS,
):
    operations_pages.append(validation_page)

if has_any_permission(
    current_user,
    PERMISSION_MANAGE_EVACUATION_CENTERS,
    PERMISSION_SUBMIT_EVACUATION_UPDATES,
):
    operations_pages.append(evacuation_centers_page)

if has_permission(current_user, PERMISSION_MANAGE_INCIDENTS):
    operations_pages.append(incidents_page)


navigation_sections = {}

if operations_pages:
    navigation_sections["Operations"] = operations_pages

if has_permission(current_user, PERMISSION_VIEW_REPORTS):
    navigation_sections["Reporting"] = [reports_page]

if has_permission(current_user, PERMISSION_MANAGE_USERS):
    navigation_sections["Administration"] = [user_admin_page]

if not navigation_sections:
    st.error("Your role has no assigned application pages.")
    st.stop()


selected_page = st.navigation(navigation_sections)
selected_page.run()
'@

Set-Content -Path app.py -Value $appContent -Encoding UTF8
Write-Host "app.py updated. Backup created." -ForegroundColor Green

Step "Running Python syntax checks"

python -m py_compile `
    app.py `
    pages\user_admin.py `
    pages\validation.py `
    services\user_admin_service.py `
    services\validation_service.py

if ($LASTEXITCODE -ne 0) {
    throw "Python syntax check failed."
}

Step "Applying already-generated Alembic migrations"

alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    throw "alembic upgrade head failed."
}

Step "Checking reviewed_by_user_id in PostgreSQL"

$columnCheck = python -c "from sqlalchemy import inspect; from database.connection import engine; cols={c['name'] for c in inspect(engine).get_columns('barangay_updates')}; print('YES' if 'reviewed_by_user_id' in cols else 'NO')"
$columnCheck = ($columnCheck | Select-Object -Last 1).Trim()

if ($columnCheck -eq "NO") {
    Step "Generating Phase 13B migration"

    alembic revision --autogenerate -m "link barangay reviews to app users"
    if ($LASTEXITCODE -ne 0) {
        throw "Alembic autogeneration failed."
    }

    Step "Applying Phase 13B migration"

    alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Applying the migration failed."
    }
}
elseif ($columnCheck -eq "YES") {
    Write-Host "Audit-link column already exists; no new migration needed." -ForegroundColor Yellow
}
else {
    throw "Could not determine column state: $columnCheck"
}

Step "Checking Alembic consistency"

alembic check
if ($LASTEXITCODE -ne 0) {
    throw "Alembic still detects unapplied model changes."
}

Step "Running import tests"

python -c "from services.user_admin_service import list_app_users, create_app_user, update_app_user; print('User administration service: OK')"
if ($LASTEXITCODE -ne 0) { throw "User admin import failed." }

python -c "from services.validation_service import review_barangay_update; print('Authenticated validation service: OK')"
if ($LASTEXITCODE -ne 0) { throw "Validation service import failed." }

python -c "from config.access_control import PERMISSION_MANAGE_USERS; print('User-management permission: OK')"
if ($LASTEXITCODE -ne 0) { throw "Permission import failed." }

Step "Verifying database"

python -c "from sqlalchemy import inspect, text; from database.connection import engine; i=inspect(engine); print('app_users table:', 'OK' if 'app_users' in i.get_table_names() else 'MISSING'); print('reviewed_by_user_id:', 'OK' if 'reviewed_by_user_id' in {c['name'] for c in i.get_columns('barangay_updates')} else 'MISSING'); print('app_users count:', engine.connect().execute(text('SELECT COUNT(*) FROM app_users')).scalar_one())"

if ($LASTEXITCODE -ne 0) {
    throw "Database verification failed."
}

Step "Reviewing Git state"
git status --short

if (-not $SkipCommit) {
    Step "Staging Phase 13B"

    git add `
        config\access_control.py `
        database\models.py `
        database\repositories.py `
        database\migrations\ `
        services\user_admin_service.py `
        services\validation_service.py `
        pages\user_admin.py `
        pages\validation.py `
        app.py

    if (git diff --cached --name-only | Select-String -SimpleMatch ".streamlit/secrets.toml") {
        git restore --staged .streamlit/secrets.toml
        throw "Security stop: secrets.toml was staged and has been unstaged."
    }

    Write-Host ""
    Write-Host "Staged files:" -ForegroundColor Cyan
    git diff --cached --name-only

    Step "Committing Phase 13B"

    git commit -m "Add user administration and authenticated review auditing"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "No new commit was created. The changes may already be committed." -ForegroundColor Yellow
    }

    Step "Final Git state"
    git status
    git log --oneline -7
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "PHASE 13B AUTOMATION COMPLETE" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Start the app with:" -ForegroundColor Cyan
Write-Host "  python -m streamlit run app.py"
Write-Host ""
Write-Host "Only four manual checks remain:" -ForegroundColor Cyan
Write-Host "  1. Administration -> User Administration is visible."
Write-Host "  2. Your own Administrator cannot be deactivated or demoted."
Write-Host "  3. Report Validation shows your signed-in identity automatically."
Write-Host "  4. Validate one NEW development barangay report."
Write-Host ""
Write-Host "Send 'done' if all pass, or paste the first error."
