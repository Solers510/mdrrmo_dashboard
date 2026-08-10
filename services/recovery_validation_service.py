from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from database.connection import DATABASE_URL
from services.backup_service import (
    BackupServiceError,
    create_database_backup,
    database_connection_parts,
    find_postgresql_tool,
    verify_backup_archive,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = (
    PROJECT_ROOT
    / "deployment"
    / "PHASE8_VALIDATION_RESULTS.json"
)
MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

RESTORE_PREFIX = "mdrrmo_restore_test_"
MIGRATION_PREFIX = "mdrrmo_migration_test_"

REQUIRED_IMMUTABILITY_TRIGGERS = {
    "trg_report_snapshots_immutable",
    "trg_system_audit_log_immutable",
}


class RecoveryValidationError(Exception):
    """Raised when a deployment/recovery validation step fails."""


def _temporary_database_name(prefix: str) -> str:
    return (
        prefix
        + datetime.now(
            MANILA_TIMEZONE
        ).strftime("%Y%m%d_%H%M%S_%f")
    )


def _maintenance_connection(
    *,
    username: str,
    password: str,
) -> psycopg.Connection:
    parts = database_connection_parts()

    return psycopg.connect(
        host=parts["host"],
        port=parts["port"],
        user=username,
        password=password,
        dbname="postgres",
        autocommit=True,
        connect_timeout=5,
    )


def _verify_maintenance_role(
    connection: psycopg.Connection,
) -> dict[str, object]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                current_user,
                rolsuper,
                rolcreatedb,
                rolcreaterole
            FROM pg_roles
            WHERE rolname = current_user
            """
        )
        row = cursor.fetchone()

    if row is None:
        raise RecoveryValidationError(
            "The maintenance PostgreSQL role could not be inspected."
        )

    role_name = str(row[0])
    is_superuser = bool(row[1])
    can_create_database = bool(row[2])
    can_create_role = bool(row[3])

    if not (
        is_superuser
        or can_create_database
    ):
        raise RecoveryValidationError(
            "The maintenance role does not have CREATEDB permission."
        )

    return {
        "role_name": role_name,
        "is_superuser": is_superuser,
        "can_create_database": can_create_database,
        "can_create_role": can_create_role,
    }


def _source_schema_contract() -> dict[str, object]:
    parts = database_connection_parts()

    connection = psycopg.connect(
        host=parts["host"],
        port=parts["port"],
        user=parts["username"],
        password=parts["password"],
        dbname=parts["database"],
        connect_timeout=5,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
            tables = [
                str(row[0])
                for row in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT tgname
                FROM pg_trigger
                WHERE NOT tgisinternal
                ORDER BY tgname
                """
            )
            triggers = [
                str(row[0])
                for row in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT version_num
                FROM alembic_version
                LIMIT 1
                """
            )
            revision_row = cursor.fetchone()

    finally:
        connection.close()

    if not revision_row:
        raise RecoveryValidationError(
            "Source database has no Alembic revision."
        )

    return {
        "tables": tables,
        "triggers": triggers,
        "alembic_revision": str(
            revision_row[0]
        ),
    }


def _create_disposable_database(
    *,
    maintenance_connection:
        psycopg.Connection,
    database_name: str,
    application_role: str,
    maintenance_username: str,
    maintenance_password: str,
) -> None:
    with maintenance_connection.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                "CREATE DATABASE {} TEMPLATE template0"
            ).format(
                sql.Identifier(database_name)
            )
        )

        cursor.execute(
            sql.SQL(
                "GRANT CONNECT ON DATABASE {} TO {}"
            ).format(
                sql.Identifier(database_name),
                sql.Identifier(application_role),
            )
        )

    parts = database_connection_parts()

    database_connection = psycopg.connect(
        host=parts["host"],
        port=parts["port"],
        user=maintenance_username,
        password=maintenance_password,
        dbname=database_name,
        autocommit=True,
        connect_timeout=5,
    )

    try:
        with database_connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    "GRANT USAGE, CREATE "
                    "ON SCHEMA public TO {}"
                ).format(
                    sql.Identifier(
                        application_role
                    )
                )
            )
    finally:
        database_connection.close()


def _drop_disposable_database(
    *,
    maintenance_connection:
        psycopg.Connection,
    database_name: str,
) -> None:
    with maintenance_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s
              AND pid <> pg_backend_pid()
            """,
            (database_name,),
        )
        cursor.execute(
            sql.SQL(
                "DROP DATABASE IF EXISTS {}"
            ).format(
                sql.Identifier(database_name)
            )
        )


def _application_connection(
    database_name: str,
) -> psycopg.Connection:
    parts = database_connection_parts()

    return psycopg.connect(
        host=parts["host"],
        port=parts["port"],
        user=parts["username"],
        password=parts["password"],
        dbname=database_name,
        connect_timeout=5,
    )


def _application_database_url(
    database_name: str,
) -> str:
    url = make_url(DATABASE_URL)
    target = url.set(
        database=database_name
    )
    return target.render_as_string(
        hide_password=False
    )


def _verify_schema(
    *,
    database_name: str,
    expected_tables: list[str],
    expected_triggers: list[str],
    expected_revision: str,
) -> dict[str, object]:
    connection = _application_connection(
        database_name
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
            actual_tables = [
                str(row[0])
                for row in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT tgname
                FROM pg_trigger
                WHERE NOT tgisinternal
                ORDER BY tgname
                """
            )
            actual_triggers = [
                str(row[0])
                for row in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT version_num
                FROM alembic_version
                LIMIT 1
                """
            )
            revision_row = cursor.fetchone()

    finally:
        connection.close()

    actual_revision = (
        str(revision_row[0])
        if revision_row
        else ""
    )

    if actual_tables != expected_tables:
        raise RecoveryValidationError(
            "Disposable database table set does not match "
            "the source schema."
        )

    if actual_triggers != expected_triggers:
        raise RecoveryValidationError(
            "Disposable database trigger set does not match "
            "the source schema."
        )

    if actual_revision != expected_revision:
        raise RecoveryValidationError(
            "Disposable database Alembic revision does not match."
        )

    missing_immutability = (
        REQUIRED_IMMUTABILITY_TRIGGERS
        - set(actual_triggers)
    )

    if missing_immutability:
        raise RecoveryValidationError(
            "Disposable database is missing immutability triggers: "
            + ", ".join(
                sorted(missing_immutability)
            )
        )

    return {
        "tables": actual_tables,
        "triggers": actual_triggers,
        "alembic_revision":
            actual_revision,
    }


def _restore_backup_as_application_role(
    *,
    backup_path: Path,
    database_name: str,
) -> None:
    parts = database_connection_parts()
    pg_restore = find_postgresql_tool(
        "pg_restore"
    )

    if pg_restore is None:
        raise RecoveryValidationError(
            "pg_restore was not found."
        )

    environment = os.environ.copy()
    environment[
        "PGPASSWORD"
    ] = parts["password"]

    result = subprocess.run(
        [
            str(pg_restore),
            "--host",
            parts["host"],
            "--port",
            str(parts["port"]),
            "--username",
            parts["username"],
            "--dbname",
            database_name,
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
        raise RecoveryValidationError(
            "pg_restore failed during the disposable restore drill."
        )


def _verify_restored_counts(
    *,
    database_name: str,
    metadata: dict[str, Any],
) -> None:
    connection = _application_connection(
        database_name
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT version_num
                FROM alembic_version
                LIMIT 1
                """
            )
            revision_row = cursor.fetchone()

            revision = (
                str(revision_row[0])
                if revision_row
                else ""
            )

            if revision != str(
                metadata.get(
                    "alembic_revision",
                    "",
                )
            ):
                raise RecoveryValidationError(
                    "Restored Alembic revision does not match "
                    "backup metadata."
                )

            for (
                table_name,
                expected_count,
            ) in metadata.get(
                "table_counts",
                {},
            ).items():
                cursor.execute(
                    sql.SQL(
                        "SELECT COUNT(*) FROM {}"
                    ).format(
                        sql.Identifier(
                            str(table_name)
                        )
                    )
                )
                actual_count = int(
                    cursor.fetchone()[0]
                )

                if (
                    actual_count
                    != int(expected_count)
                ):
                    raise RecoveryValidationError(
                        "Restored row-count mismatch for "
                        f"{table_name}: expected "
                        f"{expected_count}, got "
                        f"{actual_count}."
                    )
    finally:
        connection.close()


def run_restore_drill(
    *,
    maintenance_username: str,
    maintenance_password: str,
    backup_path: Path,
    source_schema:
        dict[str, object],
) -> dict[str, object]:
    backup_path = backup_path.resolve()
    metadata_path = backup_path.with_suffix(
        ".json"
    )

    if not metadata_path.exists():
        raise RecoveryValidationError(
            "Backup metadata JSON is missing."
        )

    metadata = json.loads(
        metadata_path.read_text(
            encoding="utf-8"
        )
    )

    try:
        verification = verify_backup_archive(
            backup_path,
            expected_sha256=str(
                metadata["sha256"]
            ),
        )
    except BackupServiceError as error:
        raise RecoveryValidationError(
            str(error)
        ) from error

    parts = database_connection_parts()

    if (
        maintenance_username.strip().lower()
        == str(
            parts["username"]
        ).strip().lower()
    ):
        raise RecoveryValidationError(
            "Maintenance role must be separate "
            "from the normal application role."
        )

    maintenance = _maintenance_connection(
        username=maintenance_username,
        password=maintenance_password,
    )

    database_name = (
        _temporary_database_name(
            RESTORE_PREFIX
        )
    )

    try:
        role_info = (
            _verify_maintenance_role(
                maintenance
            )
        )

        _create_disposable_database(
            maintenance_connection=
                maintenance,
            database_name=database_name,
            application_role=str(
                parts["username"]
            ),
            maintenance_username=
                maintenance_username,
            maintenance_password=
                maintenance_password,
        )

        _restore_backup_as_application_role(
            backup_path=backup_path,
            database_name=database_name,
        )

        _verify_restored_counts(
            database_name=database_name,
            metadata=metadata,
        )

        schema_result = _verify_schema(
            database_name=database_name,
            expected_tables=list(
                source_schema[
                    "tables"
                ]
            ),
            expected_triggers=list(
                source_schema[
                    "triggers"
                ]
            ),
            expected_revision=str(
                source_schema[
                    "alembic_revision"
                ]
            ),
        )

        return {
            "status": "PASS",
            "temporary_database":
                database_name,
            "maintenance_role":
                role_info["role_name"],
            "application_role":
                parts["username"],
            "backup_filename":
                backup_path.name,
            "backup_sha256":
                verification["sha256"],
            "backup_size_bytes":
                verification["size_bytes"],
            "alembic_revision":
                schema_result[
                    "alembic_revision"
                ],
            "table_count":
                len(
                    schema_result[
                        "tables"
                    ]
                ),
            "trigger_count":
                len(
                    schema_result[
                        "triggers"
                    ]
                ),
            "row_counts_matched":
                True,
            "application_role_restore":
                True,
        }

    finally:
        try:
            _drop_disposable_database(
                maintenance_connection=
                    maintenance,
                database_name=database_name,
            )
        finally:
            maintenance.close()


def run_fresh_database_drill(
    *,
    maintenance_username: str,
    maintenance_password: str,
    source_schema:
        dict[str, object],
) -> dict[str, object]:
    parts = database_connection_parts()

    if (
        maintenance_username.strip().lower()
        == str(
            parts["username"]
        ).strip().lower()
    ):
        raise RecoveryValidationError(
            "Maintenance role must be separate "
            "from the normal application role."
        )

    maintenance = _maintenance_connection(
        username=maintenance_username,
        password=maintenance_password,
    )

    database_name = (
        _temporary_database_name(
            MIGRATION_PREFIX
        )
    )

    try:
        role_info = (
            _verify_maintenance_role(
                maintenance
            )
        )

        _create_disposable_database(
            maintenance_connection=
                maintenance,
            database_name=database_name,
            application_role=str(
                parts["username"]
            ),
            maintenance_username=
                maintenance_username,
            maintenance_password=
                maintenance_password,
        )

        environment = os.environ.copy()
        environment[
            "DATABASE_URL"
        ] = _application_database_url(
            database_name
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
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RecoveryValidationError(
                "Alembic zero-to-head migration failed "
                "in the disposable database."
            )

        schema_result = _verify_schema(
            database_name=database_name,
            expected_tables=list(
                source_schema[
                    "tables"
                ]
            ),
            expected_triggers=list(
                source_schema[
                    "triggers"
                ]
            ),
            expected_revision=str(
                source_schema[
                    "alembic_revision"
                ]
            ),
        )

        return {
            "status": "PASS",
            "temporary_database":
                database_name,
            "maintenance_role":
                role_info["role_name"],
            "application_role":
                parts["username"],
            "alembic_revision":
                schema_result[
                    "alembic_revision"
                ],
            "table_count":
                len(
                    schema_result[
                        "tables"
                    ]
                ),
            "trigger_count":
                len(
                    schema_result[
                        "triggers"
                    ]
                ),
            "application_role_migration":
                True,
        }

    finally:
        try:
            _drop_disposable_database(
                maintenance_connection=
                    maintenance,
                database_name=database_name,
            )
        finally:
            maintenance.close()


def run_phase8_validation(
    *,
    maintenance_username: str,
    maintenance_password: str,
) -> dict[str, object]:
    source_schema = (
        _source_schema_contract()
    )

    backup = create_database_backup()
    backup_path = Path(
        str(
            backup[
                "backup_path"
            ]
        )
    )

    restore = run_restore_drill(
        maintenance_username=
            maintenance_username,
        maintenance_password=
            maintenance_password,
        backup_path=backup_path,
        source_schema=source_schema,
    )

    migration = (
        run_fresh_database_drill(
            maintenance_username=
                maintenance_username,
            maintenance_password=
                maintenance_password,
            source_schema=source_schema,
        )
    )

    evidence = {
        "status": "PASS",
        "validated_at":
            datetime.now(
                MANILA_TIMEZONE
            ).isoformat(),
        "source_database":
            database_connection_parts()[
                "database"
            ],
        "alembic_revision":
            source_schema[
                "alembic_revision"
            ],
        "backup": {
            "filename":
                backup_path.name,
            "sha256":
                backup[
                    "sha256"
                ],
            "archive_verified":
                backup[
                    "archive_verified"
                ],
        },
        "restore_drill": restore,
        "fresh_database_drill":
            migration,
        "temporary_databases_removed":
            True,
    }

    EVIDENCE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    EVIDENCE_PATH.write_text(
        json.dumps(
            evidence,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return evidence
