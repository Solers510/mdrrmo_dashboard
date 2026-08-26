from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import tomllib
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.runtime import normalize_database_url  # noqa: E402


FORBIDDEN_TRACKED_FILES = {
    ".env",
    ".streamlit/secrets.toml",
    "deployment/production_environment.toml",
    "deployment/offsite_backup_receipt.json",
}


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def repository_checks() -> list[Check]:
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    normalized = {line.strip().replace("\\", "/") for line in tracked}
    forbidden = sorted(normalized & FORBIDDEN_TRACKED_FILES)
    runtime_artifacts = sorted(
        path
        for path in normalized
        if (
            path.startswith("backups/") and path != "backups/.gitkeep"
        )
        or path.endswith((".backup", ".sha256"))
    )

    checks = [
        Check(
            "Protected configuration",
            "PASS" if not forbidden else "FAIL",
            "No protected configuration file is tracked."
            if not forbidden
            else "Tracked protected files: " + ", ".join(forbidden),
        ),
        Check(
            "Backup artifacts",
            "PASS" if not runtime_artifacts else "FAIL",
            "No database backup artifact is tracked."
            if not runtime_artifacts
            else "Tracked backup artifacts: " + ", ".join(runtime_artifacts),
        ),
    ]

    cloud_template = (
        PROJECT_ROOT / ".streamlit" / "secrets.cloud.example.toml"
    )
    checks.append(
        Check(
            "Cloud secrets template",
            "PASS" if cloud_template.is_file() else "FAIL",
            "Placeholder-only cloud template is present."
            if cloud_template.is_file()
            else "Cloud secrets template is missing.",
        )
    )

    runbook = PROJECT_ROOT / "deployment" / "CLOUD_PILOT_RUNBOOK.md"
    checks.append(
        Check(
            "Cloud pilot runbook",
            "PASS" if runbook.is_file() else "FAIL",
            "Cloud pilot and rollback guidance is present."
            if runbook.is_file()
            else "Cloud pilot runbook is missing.",
        )
    )

    decision_checklist = (
        PROJECT_ROOT / "deployment" / "CLOUD_PILOT_DECISION_CHECKLIST.md"
    )
    checks.append(
        Check(
            "Management decision checklist",
            "PASS" if decision_checklist.is_file() else "FAIL",
            "Plain-language management decision checklist is present."
            if decision_checklist.is_file()
            else "Management decision checklist is missing.",
        )
    )
    return checks


def secret_checks(path: Path | None) -> list[Check]:
    if path is None:
        return [
            Check(
                "Private cloud configuration",
                "MANUAL",
                "Provide --secrets-file only after the protected staging "
                "configuration has been created.",
            )
        ]

    if not path.is_file():
        return [
            Check(
                "Private cloud configuration",
                "FAIL",
                f"Secrets file not found: {path}",
            )
        ]

    try:
        values = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        return [
            Check(
                "Private cloud configuration",
                "FAIL",
                f"Secrets file could not be parsed: {type(error).__name__}.",
            )
        ]

    checks: list[Check] = []
    mode = str(values.get("APP_DEPLOYMENT_MODE", "")).strip().lower()
    checks.append(
        Check(
            "Cloud deployment mode",
            "PASS" if mode == "cloud" else "FAIL",
            "APP_DEPLOYMENT_MODE is cloud."
            if mode == "cloud"
            else "APP_DEPLOYMENT_MODE must be cloud.",
        )
    )

    raw_database_url = str(values.get("DATABASE_URL", "")).strip()
    parsed_database_url = urlparse(normalize_database_url(raw_database_url))
    database_host = str(parsed_database_url.hostname or "").lower()
    database_valid = (
        parsed_database_url.scheme == "postgresql+psycopg"
        and bool(database_host)
        and database_host not in {"localhost", "127.0.0.1", "::1"}
        and "replace_" not in raw_database_url.lower()
    )
    checks.append(
        Check(
            "Cloud database endpoint",
            "PASS" if database_valid else "FAIL",
            f"Remote PostgreSQL host configured: {database_host}."
            if database_valid
            else "DATABASE_URL must contain a populated remote PostgreSQL host.",
        )
    )

    sslmode = str(values.get("DB_SSLMODE", "require")).strip().lower()
    ssl_valid = sslmode in {"require", "verify-ca", "verify-full"}
    checks.append(
        Check(
            "Database TLS policy",
            "PASS" if ssl_valid else "FAIL",
            f"DB_SSLMODE={sslmode}."
            if ssl_valid
            else "DB_SSLMODE must be require, verify-ca, or verify-full.",
        )
    )

    auth = values.get("auth", {})
    redirect_uri = str(auth.get("redirect_uri", "")).strip()
    parsed_redirect = urlparse(redirect_uri)
    redirect_valid = (
        parsed_redirect.scheme == "https"
        and str(parsed_redirect.hostname or "").endswith(".streamlit.app")
        and parsed_redirect.path == "/oauth2callback"
        and "replace_" not in redirect_uri.lower()
    )
    checks.append(
        Check(
            "Cloud OIDC callback",
            "PASS" if redirect_valid else "FAIL",
            "HTTPS Streamlit callback is populated."
            if redirect_valid
            else "Use the final HTTPS streamlit.app /oauth2callback URL.",
        )
    )

    placeholders = [
        name
        for name, value in (
            ("cookie_secret", auth.get("cookie_secret")),
            ("client_id", auth.get("client_id")),
            ("client_secret", auth.get("client_secret")),
        )
        if not str(value or "").strip()
        or "replace_" in str(value).lower()
    ]
    checks.append(
        Check(
            "OIDC protected values",
            "PASS" if not placeholders else "FAIL",
            "Required OIDC protected values are populated."
            if not placeholders
            else "Missing or placeholder values: " + ", ".join(placeholders),
        )
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Phase 11D cloud-pilot repository and secrets."
    )
    parser.add_argument(
        "--secrets-file",
        type=Path,
        help="Optional path to a protected, populated Streamlit secrets file.",
    )
    args = parser.parse_args()

    checks = [*repository_checks(), *secret_checks(args.secrets_file)]
    print("MDRRMO PHASE 11D CLOUD-PILOT PREFLIGHT")
    for check in checks:
        print(f"[{check.status}] {check.name}: {check.detail}")

    failed = any(check.status == "FAIL" for check in checks)
    print("RESULT: " + ("FAIL" if failed else "PASS WITH MANUAL GATES"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
