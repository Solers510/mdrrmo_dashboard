from __future__ import annotations

import json
from pathlib import Path
import tomllib
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_PATH = PROJECT_ROOT / "deployment" / "production_environment.toml"
PHASE8_PATH = PROJECT_ROOT / "deployment" / "PHASE8_VALIDATION_RESULTS.json"
UAT_PATH = PROJECT_ROOT / "deployment" / "UAT_SIGNOFF.md"
SECRETS_PATH = PROJECT_ROOT / ".streamlit" / "secrets.toml"


def expected_callback(base_url: str) -> str:
    return base_url.strip().rstrip("/") + "/oauth2callback"


def validate_public_base_url(value: str) -> tuple[bool, str]:
    value = value.strip().rstrip("/")

    if not value or "REPLACE_" in value.upper():
        return False, "Production URL is still a placeholder."

    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()

    if parsed.scheme.lower() != "https":
        return False, "Production URL must use HTTPS."

    if host in {"localhost", "127.0.0.1", "::1"}:
        return False, "Production URL cannot use localhost."

    if not host or parsed.query or parsed.fragment:
        return False, "Production URL is malformed."

    return True, "Production HTTPS URL is structurally valid."


def emit(name: str, status: str, detail: str) -> dict[str, str]:
    return {"check": name, "status": status, "detail": detail}


def main() -> None:
    rows: list[dict[str, str]] = []

    if PHASE8_PATH.exists():
        evidence = json.loads(PHASE8_PATH.read_text(encoding="utf-8"))
        phase8_pass = (
            evidence.get("status") == "PASS"
            and evidence.get("restore_drill", {}).get("status") == "PASS"
            and evidence.get("fresh_database_drill", {}).get("status") == "PASS"
            and evidence.get("temporary_databases_removed") is True
        )
        rows.append(
            emit(
                "Phase 8 recovery validation",
                "PASS" if phase8_pass else "FAIL",
                "Restore and fresh-database evidence is complete."
                if phase8_pass
                else "Phase 8 evidence is incomplete.",
            )
        )
    else:
        rows.append(emit("Phase 8 recovery validation", "FAIL", "Evidence file missing."))

    if UAT_PATH.exists() and "**Status: COMPLETE**" in UAT_PATH.read_text(encoding="utf-8-sig"):
        rows.append(emit("Functional UAT", "PASS", "UAT sign-off is recorded as COMPLETE."))
    else:
        rows.append(emit("Functional UAT", "FAIL", "UAT sign-off is missing or incomplete."))

    if not ENVIRONMENT_PATH.exists():
        rows.append(
            emit(
                "Production environment",
                "MANUAL",
                "Create deployment/production_environment.toml from the tracked example after the production host is selected.",
            )
        )
    else:
        env = tomllib.loads(ENVIRONMENT_PATH.read_text(encoding="utf-8-sig"))
        base_url = str(env.get("public_base_url", ""))
        valid, detail = validate_public_base_url(base_url)
        rows.append(emit("Production HTTPS URL", "PASS" if valid else "FAIL", detail))

        address = str(env.get("streamlit_address", "")).strip()
        rows.append(
            emit(
                "Streamlit loopback binding",
                "PASS" if address in {"127.0.0.1", "::1"} else "FAIL",
                f"Configured address: {address or '(missing)'}.",
            )
        )

        callback = str(env.get("expected_oidc_callback", "")).strip()
        required = expected_callback(base_url) if valid else ""
        rows.append(
            emit(
                "OIDC callback contract",
                "PASS" if valid and callback == required else "FAIL",
                "Callback equals <public_base_url>/oauth2callback."
                if valid and callback == required
                else f"Expected: {required or 'final HTTPS base URL + /oauth2callback'}",
            )
        )

        if SECRETS_PATH.exists() and valid:
            secrets = tomllib.loads(SECRETS_PATH.read_text(encoding="utf-8-sig"))
            actual = str(secrets.get("auth", {}).get("redirect_uri", "")).strip()
            rows.append(
                emit(
                    "Streamlit production OIDC redirect",
                    "PASS" if actual == required else "MANUAL",
                    "secrets.toml matches production callback."
                    if actual == required
                    else "Update Streamlit secrets and the Google OIDC client to the final production callback.",
                )
            )

        proxy = str(env.get("reverse_proxy", "")).strip()
        rows.append(
            emit(
                "Reverse proxy selected",
                "PASS" if proxy and "REPLACE_" not in proxy.upper() else "MANUAL",
                f"Configured value: {proxy or '(missing)'}.",
            )
        )

        backup_dest = str(env.get("off_machine_backup_destination", "")).strip()
        rows.append(
            emit(
                "Off-machine backup destination",
                "PASS" if backup_dest and "REPLACE_" not in backup_dest.upper() else "MANUAL",
                "Approved destination is declared."
                if backup_dest and "REPLACE_" not in backup_dest.upper()
                else "Select an approved NAS/network/off-machine destination.",
            )
        )

    rows.extend(
        [
            emit("Authoritative barangay/PSGC data", "MANUAL", "Requires MDRRMO/LGU approval."),
            emit("Alert-level definitions", "MANUAL", "Requires MDRRMO approval."),
            emit("Report-layout decision", "MANUAL", "Office must accept current exports or provide official templates."),
            emit("Live HTTPS/TLS/network check", "MANUAL", "Run after the production endpoint exists."),
        ]
    )

    print("")
    print("MDRRMO PHASE 9 PRODUCTION READINESS")
    print("=" * 72)

    for row in rows:
        print(f"[{row['status']:<6}] {row['check']}: {row['detail']}")

    failures = [row for row in rows if row["status"] == "FAIL"]
    manual = [row for row in rows if row["status"] == "MANUAL"]

    print("")
    print("SUMMARY")
    print("-" * 72)
    print(f"Automated failures: {len(failures)}")
    print(f"Manual/open gates: {len(manual)}")

    if failures:
        print("PRODUCTION READINESS: FAIL")
        raise SystemExit(1)

    if manual:
        print("PRODUCTION READINESS: NOT YET - open gates remain.")
        return

    print("PRODUCTION READINESS: PASS")


if __name__ == "__main__":
    main()
