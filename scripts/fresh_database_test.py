from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_TABLES = {
    "disaster_events",
    "barangays",
    "barangay_updates",
    "evacuation_centers",
    "evacuation_center_updates",
    "app_users",
    "report_snapshots",
    "system_audit_log",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Test a zero-to-head Alembic migration against an explicitly "
            "provided EMPTY disposable PostgreSQL database."
        )
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help=(
            "Disposable test database URL. The database name must contain "
            "'test' or 'uat'."
        ),
    )
    args = parser.parse_args()

    target_url = make_url(
        args.database_url
    )

    if not target_url.drivername.startswith(
        "postgresql"
    ):
        raise SystemExit(
            "FRESH DATABASE TEST BLOCKED: PostgreSQL URL required."
        )

    target_database = str(
        target_url.database
        or ""
    )

    if (
        "test"
        not in target_database.lower()
        and "uat"
        not in target_database.lower()
    ):
        raise SystemExit(
            "FRESH DATABASE TEST BLOCKED: target database name must "
            "contain 'test' or 'uat'."
        )

    production_url = os.getenv(
        "DATABASE_URL",
        "",
    )

    if production_url:
        production_database = str(
            make_url(
                production_url
            ).database
            or ""
        )

        if (
            production_database.lower()
            == target_database.lower()
        ):
            raise SystemExit(
                "FRESH DATABASE TEST BLOCKED: target database name "
                "matches the configured application database."
            )

    connection = psycopg.connect(
        host=target_url.host or "localhost",
        port=int(
            target_url.port
            or 5432
        ),
        user=target_url.username,
        password=target_url.password,
        dbname=target_database,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                """
            )
            existing_tables = {
                row[0]
                for row in cursor.fetchall()
            }

        if existing_tables:
            raise SystemExit(
                "FRESH DATABASE TEST BLOCKED: target database is not empty. "
                "Existing tables: "
                + ", ".join(
                    sorted(
                        existing_tables
                    )
                )
            )
    finally:
        connection.close()

    environment = os.environ.copy()
    environment[
        "DATABASE_URL"
    ] = args.database_url

    print(
        "Running Alembic zero-to-head migration "
        f"against disposable database {target_database!r}..."
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "upgrade",
            "head",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise SystemExit(
            "FRESH DATABASE TEST: FAIL"
        )

    connection = psycopg.connect(
        host=target_url.host or "localhost",
        port=int(
            target_url.port
            or 5432
        ),
        user=target_url.username,
        password=target_url.password,
        dbname=target_database,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                """
            )
            tables = {
                row[0]
                for row in cursor.fetchall()
            }

            missing = (
                REQUIRED_TABLES
                - tables
            )

            if missing:
                raise SystemExit(
                    "FRESH DATABASE TEST: FAIL - missing tables: "
                    + ", ".join(
                        sorted(missing)
                    )
                )

            cursor.execute(
                "SELECT version_num "
                "FROM alembic_version "
                "LIMIT 1"
            )
            revision = cursor.fetchone()

            if not revision:
                raise SystemExit(
                    "FRESH DATABASE TEST: FAIL - "
                    "alembic_version is empty."
                )

    finally:
        connection.close()

    print(
        "FRESH DATABASE TEST: PASS"
    )
    print(
        f"Database: {target_database}"
    )
    print(
        f"Alembic revision: {revision[0]}"
    )
    print(
        "The disposable database was intentionally left in place "
        "for inspection. Drop it later using a maintenance account."
    )


if __name__ == "__main__":
    main()
