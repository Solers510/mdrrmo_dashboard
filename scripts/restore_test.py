from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql

from services.backup_service import (
    DEFAULT_BACKUP_DIRECTORY,
    BackupServiceError,
    database_connection_parts,
    find_postgresql_tool,
    verify_backup_archive,
)

MANILA_TIMEZONE = ZoneInfo("Asia/Manila")


def latest_backup() -> Path | None:
    backups = sorted(
        DEFAULT_BACKUP_DIRECTORY.glob("*.backup"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return backups[0] if backups else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Restore a backup into a temporary PostgreSQL database, "
            "verify it, then remove the temporary database."
        )
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--backup", type=Path)
    selection.add_argument("--latest", action="store_true")
    args = parser.parse_args()

    backup_path = latest_backup() if args.latest else args.backup
    if backup_path is None:
        raise SystemExit("RESTORE TEST BLOCKED: no backup archive was found.")

    backup_path = backup_path.resolve()
    metadata_path = backup_path.with_suffix(".json")
    if not metadata_path.exists():
        raise SystemExit(
            "RESTORE TEST BLOCKED: backup metadata JSON is missing."
        )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    try:
        verify_backup_archive(
            backup_path,
            expected_sha256=str(metadata["sha256"]),
        )
    except BackupServiceError as error:
        raise SystemExit(f"RESTORE TEST BLOCKED: {error}")

    connection = database_connection_parts()
    pg_restore = find_postgresql_tool("pg_restore")
    if pg_restore is None:
        raise SystemExit("RESTORE TEST BLOCKED: pg_restore was not found.")

    temporary_database = (
        "mdrrmo_restore_test_"
        + datetime.now(MANILA_TIMEZONE).strftime("%Y%m%d_%H%M%S")
    )

    maintenance_connection = None

    try:
        maintenance_connection = psycopg.connect(
            host=connection["host"],
            port=connection["port"],
            user=connection["username"],
            password=connection["password"],
            dbname="postgres",
            autocommit=True,
        )

        with maintenance_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rolsuper, rolcreatedb
                FROM pg_roles
                WHERE rolname = current_user
                """
            )
            permission_row = cursor.fetchone()
            can_create_database = bool(
                permission_row
                and (permission_row[0] or permission_row[1])
            )

            if not can_create_database:
                print(
                    "RESTORE TEST BLOCKED: the configured application "
                    "PostgreSQL role does not have CREATEDB permission."
                )
                print(
                    "This is not a backup failure. A full restore drill "
                    "remains an open deployment gate."
                )
                raise SystemExit(2)

            cursor.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(temporary_database)
                )
            )

        environment = os.environ.copy()
        environment["PGPASSWORD"] = connection["password"]

        result = subprocess.run(
            [
                str(pg_restore),
                "--host", connection["host"],
                "--port", str(connection["port"]),
                "--username", connection["username"],
                "--dbname", temporary_database,
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                str(backup_path),
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError("pg_restore returned a non-zero exit code.")

        restored_connection = psycopg.connect(
            host=connection["host"],
            port=connection["port"],
            user=connection["username"],
            password=connection["password"],
            dbname=temporary_database,
        )

        try:
            with restored_connection.cursor() as cursor:
                cursor.execute("SELECT version_num FROM alembic_version LIMIT 1")
                revision = cursor.fetchone()[0]
                expected_revision = metadata.get("alembic_revision")
                if revision != expected_revision:
                    raise RuntimeError(
                        "Restored Alembic revision does not match backup metadata."
                    )

                for table_name, expected_count in metadata.get(
                    "table_counts", {}
                ).items():
                    cursor.execute(
                        sql.SQL("SELECT COUNT(*) FROM {}").format(
                            sql.Identifier(table_name)
                        )
                    )
                    actual_count = int(cursor.fetchone()[0])
                    if actual_count != int(expected_count):
                        raise RuntimeError(
                            f"Restored table count mismatch for {table_name}: "
                            f"expected {expected_count}, got {actual_count}."
                        )
        finally:
            restored_connection.close()

        print("RESTORE TEST: PASS")
        print(f"Temporary database: {temporary_database}")
        print("Alembic revision and all recorded table counts matched.")

    finally:
        if maintenance_connection is not None:
            try:
                with maintenance_connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = %s
                          AND pid <> pg_backend_pid()
                        """,
                        (temporary_database,),
                    )
                    cursor.execute(
                        sql.SQL("DROP DATABASE IF EXISTS {}").format(
                            sql.Identifier(temporary_database)
                        )
                    )
            finally:
                maintenance_connection.close()


if __name__ == "__main__":
    main()
