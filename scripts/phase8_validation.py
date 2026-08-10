from __future__ import annotations

import argparse
from getpass import getpass

from services.recovery_validation_service import (
    EVIDENCE_PATH,
    RecoveryValidationError,
    run_phase8_validation,
)


DEFAULT_MAINTENANCE_USER = (
    "mdrrmo_restore_maintenance"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the MDRRMO Phase 8 end-to-end "
            "backup restore and fresh-database validation."
        )
    )
    parser.add_argument(
        "--maintenance-user",
        default=DEFAULT_MAINTENANCE_USER,
        help=(
            "Dedicated PostgreSQL role with CREATEDB. "
            "Its password is requested securely and is "
            "not accepted on the command line."
        ),
    )
    args = parser.parse_args()

    password = getpass(
        "Maintenance PostgreSQL password: "
    )

    if not password:
        raise SystemExit(
            "PHASE 8 BLOCKED: maintenance password "
            "was empty."
        )

    try:
        evidence = run_phase8_validation(
            maintenance_username=
                args.maintenance_user,
            maintenance_password=password,
        )
    except RecoveryValidationError as error:
        raise SystemExit(
            f"PHASE 8 VALIDATION: FAIL - {error}"
        ) from error

    print("")
    print("PHASE 8 VALIDATION: PASS")
    print(
        "Verified backup created: "
        + str(
            evidence[
                "backup"
            ][
                "filename"
            ]
        )
    )
    print(
        "Restore drill: PASS "
        "(restored as the least-privilege application role)."
    )
    print(
        "Fresh database zero-to-head migration: PASS"
    )
    print(
        "Restored Alembic revision and recorded table "
        "row counts matched."
    )
    print(
        "Temporary test databases were removed."
    )
    print(
        f"Evidence: {EVIDENCE_PATH}"
    )


if __name__ == "__main__":
    main()
