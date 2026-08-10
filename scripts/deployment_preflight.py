from __future__ import annotations

import argparse
import ast
from datetime import datetime, timedelta
import importlib.metadata
from pathlib import Path
import subprocess
import sys
import tomllib
from zoneinfo import ZoneInfo

from alembic.config import Config
from alembic.script import ScriptDirectory

from config.access_control import (
    APP_ROLES,
    ROLE_ADMINISTRATOR,
    permissions_for_role,
)
from database.connection import SessionLocal
from database.repositories import fetch_all_app_users
from services.backup_service import (
    DEFAULT_BACKUP_DIRECTORY,
    verify_backup_archive,
)
from services.system_health_service import (
    overall_health_status,
    run_system_health_checks,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

EXPECTED_ROLES = {
    "Viewer",
    "Executive",
    "Encoder",
    "Validator",
    "Operations Officer",
    "Administrator",
}

REQUIRED_AUTH_KEYS = {
    "redirect_uri",
    "cookie_secret",
    "client_id",
    "client_secret",
    "server_metadata_url",
}


class PreflightFailure(Exception):
    pass


def _result(
    name: str,
    status: str,
    detail: str,
) -> dict[str, str]:
    return {
        "check": name,
        "status": status,
        "detail": detail,
    }


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PreflightFailure(
            f"Git command failed: git {' '.join(args)}"
        )
    return result.stdout.strip()


def check_git_safety() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    tracked_secrets = {
        line.strip().replace("\\", "/")
        for line in _run_git("ls-files").splitlines()
        if line.strip().replace("\\", "/")
        in {
            ".env",
            ".streamlit/secrets.toml",
        }
    }

    rows.append(
        _result(
            "Secret files are not tracked",
            "PASS" if not tracked_secrets else "FAIL",
            "No local secret file is tracked by Git."
            if not tracked_secrets
            else "Tracked secret files: "
            + ", ".join(sorted(tracked_secrets)),
        )
    )

    tracked_generated = [
        line.strip().replace("\\", "/")
        for line in _run_git("ls-files").splitlines()
        if (
            line.strip().replace("\\", "/").startswith("backups/")
            and not line.strip().endswith(".gitkeep")
        )
        or (
            line.strip().replace("\\", "/").startswith("logs/")
            and not line.strip().endswith(".gitkeep")
        )
    ]

    rows.append(
        _result(
            "Generated recovery/log artifacts are not tracked",
            "PASS" if not tracked_generated else "FAIL",
            "No backup or runtime log artifact is tracked."
            if not tracked_generated
            else "Unexpected tracked artifacts: "
            + ", ".join(tracked_generated),
        )
    )

    return rows


def check_repository_contract() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    repositories_path = (
        PROJECT_ROOT
        / "database"
        / "repositories.py"
    )
    source = repositories_path.read_text(
        encoding="utf-8-sig"
    )
    tree = ast.parse(source)

    target = "fetch_latest_evacuation_updates_for_event"
    occurrences = [
        node
        for node in tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
        and node.name == target
    ]

    rows.append(
        _result(
            "Evacuation dashboard repository contract",
            "PASS" if len(occurrences) == 1 else "FAIL",
            f"{target} definitions: {len(occurrences)}.",
        )
    )

    duplicate_names: dict[str, int] = {}
    counts: dict[str, int] = {}

    for node in tree.body:
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            counts[node.name] = counts.get(
                node.name,
                0,
            ) + 1

    duplicate_names = {
        name: count
        for name, count in counts.items()
        if count > 1
    }

    rows.append(
        _result(
            "Repository top-level function uniqueness",
            "PASS" if not duplicate_names else "FAIL",
            "No duplicate top-level repository functions."
            if not duplicate_names
            else "Duplicates: "
            + ", ".join(
                f"{name} x{count}"
                for name, count
                in sorted(duplicate_names.items())
            ),
        )
    )

    raw_exception_pages = []
    for path in (
        PROJECT_ROOT
        / "pages"
    ).glob("*.py"):
        page_source = path.read_text(
            encoding="utf-8-sig"
        )
        if "st.exception(" in page_source:
            raw_exception_pages.append(
                path.name
            )

    rows.append(
        _result(
            "Production-safe page errors",
            "PASS"
            if not raw_exception_pages
            else "FAIL",
            "No page renders raw Streamlit tracebacks."
            if not raw_exception_pages
            else "Raw traceback rendering remains in: "
            + ", ".join(raw_exception_pages),
        )
    )

    return rows


def check_role_contract() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    roles = set(APP_ROLES)
    rows.append(
        _result(
            "Application role set",
            "PASS"
            if roles == EXPECTED_ROLES
            else "FAIL",
            "Role set matches the approved prototype matrix."
            if roles == EXPECTED_ROLES
            else f"Configured roles: {sorted(roles)}",
        )
    )

    empty_roles = [
        role
        for role in APP_ROLES
        if not permissions_for_role(role)
    ]

    rows.append(
        _result(
            "Role permission coverage",
            "PASS"
            if not empty_roles
            else "FAIL",
            "Every application role has at least one permission."
            if not empty_roles
            else "Roles without permissions: "
            + ", ".join(empty_roles),
        )
    )

    try:
        with SessionLocal() as session:
            users = fetch_all_app_users(
                session
            )
    except Exception as error:
        rows.append(
            _result(
                "Authorized user role validity",
                "FAIL",
                "Could not read application accounts: "
                + type(error).__name__,
            )
        )
        return rows

    invalid_users = [
        user.email
        for user in users
        if user.role not in roles
    ]
    active_admins = [
        user
        for user in users
        if (
            user.is_active
            and user.role
            == ROLE_ADMINISTRATOR
        )
    ]

    rows.append(
        _result(
            "Authorized user role validity",
            "PASS"
            if not invalid_users
            else "FAIL",
            "All application users have known roles."
            if not invalid_users
            else "Invalid-role accounts: "
            + ", ".join(invalid_users),
        )
    )

    rows.append(
        _result(
            "Active Administrator",
            "PASS"
            if active_admins
            else "FAIL",
            f"{len(active_admins)} active Administrator account(s).",
        )
    )

    return rows


def check_auth_configuration() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    secrets_path = (
        PROJECT_ROOT
        / ".streamlit"
        / "secrets.toml"
    )

    if not secrets_path.exists():
        return [
            _result(
                "Local OIDC configuration",
                "FAIL",
                ".streamlit/secrets.toml is missing.",
            )
        ]

    try:
        data = tomllib.loads(
            secrets_path.read_text(
                encoding="utf-8-sig"
            )
        )
    except Exception as error:
        return [
            _result(
                "Local OIDC configuration",
                "FAIL",
                "Could not parse secrets.toml: "
                + type(error).__name__,
            )
        ]

    auth = data.get("auth")
    if not isinstance(auth, dict):
        return [
            _result(
                "Local OIDC configuration",
                "FAIL",
                "[auth] section is missing.",
            )
        ]

    missing = sorted(
        key
        for key in REQUIRED_AUTH_KEYS
        if not str(
            auth.get(key, "")
        ).strip()
    )

    placeholder = [
        key
        for key in (
            "cookie_secret",
            "client_id",
            "client_secret",
        )
        if "REPLACE_" in str(
            auth.get(key, "")
        ).upper()
    ]

    rows.append(
        _result(
            "Local OIDC configuration",
            "PASS"
            if not missing
            and not placeholder
            else "FAIL",
            "Required OIDC keys are populated."
            if not missing
            and not placeholder
            else (
                "Missing: "
                + ", ".join(missing)
                + (
                    "; placeholder values remain: "
                    + ", ".join(placeholder)
                    if placeholder
                    else ""
                )
            ),
        )
    )

    redirect_uri = str(
        auth.get(
            "redirect_uri",
            "",
        )
    ).strip()

    localhost_redirect = (
        "localhost" in redirect_uri.lower()
        or "127.0.0.1"
        in redirect_uri
    )

    rows.append(
        _result(
            "Production OIDC redirect",
            "MANUAL"
            if localhost_redirect
            else "PASS",
            "Current redirect is localhost; replace it with the final HTTPS "
            "deployment URL and register that URI with the OIDC provider "
            "before production."
            if localhost_redirect
            else "Redirect URI is not a localhost URL.",
        )
    )

    return rows


def check_schema() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    config = Config(
        str(
            PROJECT_ROOT
            / "alembic.ini"
        )
    )
    script_location = (
        config.get_main_option(
            "script_location"
        )
    )
    if not Path(
        script_location
    ).is_absolute():
        config.set_main_option(
            "script_location",
            str(
                PROJECT_ROOT
                / script_location
            ),
        )

    heads = ScriptDirectory.from_config(
        config
    ).get_heads()

    rows.append(
        _result(
            "Single Alembic migration head",
            "PASS"
            if len(heads) == 1
            else "FAIL",
            f"Migration heads: {heads}",
        )
    )

    return rows


def check_dependency_environment() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    requirements_path = (
        PROJECT_ROOT
        / "requirements.txt"
    )
    requirements = []

    for raw_line in requirements_path.read_text(
        encoding="utf-8-sig"
    ).splitlines():
        line = raw_line.strip()
        if (
            not line
            or line.startswith("#")
            or "==" not in line
        ):
            continue
        name, version = line.split(
            "==",
            1,
        )
        requirements.append(
            (
                name.strip(),
                version.strip(),
            )
        )

    mismatches = []

    for name, expected in requirements:
        try:
            actual = (
                importlib.metadata.version(
                    name
                )
            )
        except (
            importlib.metadata.PackageNotFoundError
        ):
            mismatches.append(
                f"{name}=missing"
            )
            continue

        if actual != expected:
            mismatches.append(
                f"{name}={actual} "
                f"(expected {expected})"
            )

    rows.append(
        _result(
            "Pinned Python dependency environment",
            "PASS"
            if not mismatches
            else "FAIL",
            "Installed package versions match requirements.txt."
            if not mismatches
            else "Mismatches: "
            + "; ".join(mismatches[:15]),
        )
    )

    rows.append(
        _result(
            "Python runtime",
            "PASS"
            if sys.version_info[:2]
            == (3, 14)
            else "MANUAL",
            f"Running Python {sys.version.split()[0]}. "
            "Prototype development baseline is Python 3.14.",
        )
    )

    return rows


def check_latest_backup(
    *,
    maximum_age_hours: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    backups = sorted(
        DEFAULT_BACKUP_DIRECTORY.glob(
            "*.backup"
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not backups:
        return [
            _result(
                "Latest verified backup",
                "FAIL",
                "No PostgreSQL backup archive exists.",
            )
        ]

    latest = backups[0]
    metadata_path = latest.with_suffix(
        ".json"
    )

    expected_hash = None
    if metadata_path.exists():
        import json

        try:
            metadata = json.loads(
                metadata_path.read_text(
                    encoding="utf-8"
                )
            )
            expected_hash = metadata.get(
                "sha256"
            )
        except Exception:
            pass

    try:
        verified = verify_backup_archive(
            latest,
            expected_sha256=expected_hash,
        )
    except Exception as error:
        rows.append(
            _result(
                "Latest verified backup",
                "FAIL",
                "Backup verification failed: "
                + type(error).__name__,
            )
        )
        return rows

    modified_at = datetime.fromtimestamp(
        latest.stat().st_mtime,
        tz=MANILA_TIMEZONE,
    )
    age = datetime.now(
        MANILA_TIMEZONE
    ) - modified_at

    rows.append(
        _result(
            "Latest verified backup",
            "PASS",
            f"{latest.name}; "
            f"{verified['size_bytes']} bytes; "
            "archive/checksum verified.",
        )
    )

    rows.append(
        _result(
            "Backup recency",
            "PASS"
            if age
            <= timedelta(
                hours=maximum_age_hours
            )
            else "MANUAL",
            f"Latest backup age: "
            f"{age.total_seconds() / 3600:.1f} hour(s).",
        )
    )

    return rows


def _uat_gate() -> dict[str, str]:
    path = (
        PROJECT_ROOT
        / "deployment"
        / "UAT_SIGNOFF.md"
    )

    if not path.exists():
        return _result(
            "Role-by-role UAT",
            "MANUAL",
            "UAT sign-off evidence is missing.",
        )

    text = path.read_text(
        encoding="utf-8-sig"
    )

    complete = (
        "**Status: COMPLETE**"
        in text
    )

    return _result(
        "Role-by-role UAT",
        "PASS" if complete else "MANUAL",
        "Deployment UAT sign-off is recorded."
        if complete
        else "UAT sign-off is not marked COMPLETE.",
    )


def _phase8_recovery_gate() -> list[dict[str, str]]:
    path = (
        PROJECT_ROOT
        / "deployment"
        / "PHASE8_VALIDATION_RESULTS.json"
    )

    if not path.exists():
        return [
            _result(
                "Full restore drill",
                "MANUAL",
                "Phase 8 restore evidence has not been generated yet.",
            ),
            _result(
                "Fresh database migration drill",
                "MANUAL",
                "Phase 8 fresh-database evidence has not been generated yet.",
            ),
        ]

    try:
        import json

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as error:
        return [
            _result(
                "Full restore drill",
                "FAIL",
                "Phase 8 evidence could not be read: "
                + type(error).__name__,
            ),
            _result(
                "Fresh database migration drill",
                "FAIL",
                "Phase 8 evidence could not be read.",
            ),
        ]

    restore_pass = (
        data.get("status") == "PASS"
        and data.get(
            "restore_drill",
            {},
        ).get("status") == "PASS"
        and data.get(
            "restore_drill",
            {},
        ).get(
            "row_counts_matched"
        )
        is True
        and data.get(
            "restore_drill",
            {},
        ).get(
            "application_role_restore"
        )
        is True
    )

    fresh_pass = (
        data.get("status") == "PASS"
        and data.get(
            "fresh_database_drill",
            {},
        ).get("status") == "PASS"
        and data.get(
            "fresh_database_drill",
            {},
        ).get(
            "application_role_migration"
        )
        is True
    )

    return [
        _result(
            "Full restore drill",
            "PASS"
            if restore_pass
            else "FAIL",
            "Verified backup restored into a disposable database, "
            "using a dedicated maintenance role for database lifecycle "
            "and the least-privilege application role for pg_restore."
            if restore_pass
            else "Phase 8 restore evidence is incomplete or failed.",
        ),
        _result(
            "Fresh database migration drill",
            "PASS"
            if fresh_pass
            else "FAIL",
            "Alembic migrated an empty disposable database from zero "
            "to head using the application role."
            if fresh_pass
            else "Phase 8 fresh-database evidence is incomplete or failed.",
        ),
    ]


def manual_gates() -> list[dict[str, str]]:
    rows = [
        _result(
            "Authoritative barangay master data",
            "MANUAL",
            "MDRRMO/LGU must verify the 30 production barangay names, PSGC "
            "codes, and active status against the authoritative list.",
        ),
        _result(
            "Alert-level definitions",
            "MANUAL",
            "MDRRMO must verify alert-level names/descriptions/operational "
            "meaning before production use.",
        ),
        _uat_gate(),
        _result(
            "Off-machine backup copy",
            "MANUAL",
            "Copy the verified backup set to approved storage outside "
            "the application machine before production.",
        ),
        _result(
            "Production network and TLS",
            "MANUAL",
            "Final hostname, HTTPS/TLS, firewall/network placement, and "
            "Google OIDC redirect registration must be verified.",
        ),
    ]

    rows[2:2] = _phase8_recovery_gate()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run MDRRMO deployment-candidate preflight checks."
        )
    )
    parser.add_argument(
        "--backup-max-age-hours",
        type=int,
        default=24,
    )
    args = parser.parse_args()

    checks: list[
        dict[str, str]
    ] = []

    checks.extend(
        check_git_safety()
    )
    checks.extend(
        check_repository_contract()
    )
    checks.extend(
        check_role_contract()
    )
    checks.extend(
        check_auth_configuration()
    )
    checks.extend(
        check_schema()
    )
    checks.extend(
        check_dependency_environment()
    )

    health = run_system_health_checks()
    checks.extend(
        {
            "check": "Health: "
            + row["check"],
            "status": row["status"],
            "detail": row["detail"],
        }
        for row in health
    )

    checks.extend(
        check_latest_backup(
            maximum_age_hours=max(
                1,
                args.backup_max_age_hours,
            )
        )
    )
    checks.extend(
        manual_gates()
    )

    print(
        "\nMDRRMO DEPLOYMENT-CANDIDATE PREFLIGHT"
    )
    print(
        "=" * 72
    )

    for row in checks:
        print(
            f"[{row['status']:<6}] "
            f"{row['check']}: "
            f"{row['detail']}"
        )

    failures = [
        row
        for row in checks
        if row["status"] == "FAIL"
    ]
    manual = [
        row
        for row in checks
        if row["status"] == "MANUAL"
    ]

    print(
        "\nSUMMARY"
    )
    print(
        "-" * 72
    )
    print(
        "Automated failures:",
        len(failures),
    )
    print(
        "Manual production gates:",
        len(manual),
    )

    if failures:
        print(
            "PROTOTYPE READINESS: FAIL"
        )
        raise SystemExit(1)

    print(
        "PROTOTYPE READINESS: PASS"
    )

    if manual:
        print(
            "PRODUCTION READINESS: NOT YET - "
            "manual gates remain."
        )
    else:
        print(
            "PRODUCTION READINESS: PASS"
        )


if __name__ == "__main__":
    main()
