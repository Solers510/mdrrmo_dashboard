from __future__ import annotations

import argparse
from getpass import getpass

import psycopg
from psycopg import sql

from services.backup_service import (
    database_connection_parts,
)


DEFAULT_MAINTENANCE_USER = (
    "mdrrmo_restore_maintenance"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create or harden the dedicated PostgreSQL "
            "maintenance role used only for restore drills."
        )
    )
    parser.add_argument(
        "--maintenance-user",
        default=DEFAULT_MAINTENANCE_USER,
    )
    parser.add_argument(
        "--admin-user",
        default="postgres",
        help=(
            "PostgreSQL administrative login used only "
            "for this setup operation."
        ),
    )
    args = parser.parse_args()

    parts = database_connection_parts()

    if (
        args.maintenance_user.strip().lower()
        == str(
            parts["username"]
        ).strip().lower()
    ):
        raise SystemExit(
            "SETUP BLOCKED: the maintenance role must "
            "not be the normal application role."
        )

    admin_password = getpass(
        f"Password for PostgreSQL administrator "
        f"{args.admin_user!r}: "
    )

    maintenance_password = getpass(
        f"New password for maintenance role "
        f"{args.maintenance_user!r}: "
    )
    maintenance_password_repeat = getpass(
        "Repeat maintenance password: "
    )

    if not admin_password:
        raise SystemExit(
            "SETUP BLOCKED: administrator password "
            "was empty."
        )

    if len(maintenance_password) < 16:
        raise SystemExit(
            "SETUP BLOCKED: choose a maintenance "
            "password of at least 16 characters."
        )

    if (
        maintenance_password
        != maintenance_password_repeat
    ):
        raise SystemExit(
            "SETUP BLOCKED: maintenance passwords "
            "did not match."
        )

    connection = psycopg.connect(
        host=parts["host"],
        port=parts["port"],
        user=args.admin_user,
        password=admin_password,
        dbname="postgres",
        autocommit=True,
        connect_timeout=5,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rolsuper, rolcreaterole
                FROM pg_roles
                WHERE rolname = current_user
                """
            )
            row = cursor.fetchone()

            if not row or not (
                bool(row[0])
                or bool(row[1])
            ):
                raise SystemExit(
                    "SETUP BLOCKED: the supplied "
                    "administrator cannot manage roles."
                )

            cursor.execute(
                """
                SELECT 1
                FROM pg_roles
                WHERE rolname = %s
                """,
                (
                    args.maintenance_user,
                ),
            )
            exists = (
                cursor.fetchone()
                is not None
            )

            if not exists:
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} "
                        "LOGIN CREATEDB "
                        "NOSUPERUSER NOCREATEROLE "
                        "NOREPLICATION NOBYPASSRLS"
                    ).format(
                        sql.Identifier(
                            args.maintenance_user
                        )
                    )
                )

            cursor.execute(
                sql.SQL(
                    "ALTER ROLE {} "
                    "LOGIN CREATEDB "
                    "NOSUPERUSER NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS "
                    "PASSWORD {}"
                ).format(
                    sql.Identifier(
                        args.maintenance_user
                    ),
                    sql.Literal(
                        maintenance_password
                    ),
                )
            )

            cursor.execute(
                """
                SELECT
                    rolname,
                    rolsuper,
                    rolcreatedb,
                    rolcreaterole,
                    rolreplication,
                    rolbypassrls
                FROM pg_roles
                WHERE rolname = %s
                """,
                (
                    args.maintenance_user,
                ),
            )
            result = cursor.fetchone()

    finally:
        connection.close()

    if result is None:
        raise SystemExit(
            "SETUP FAILED: maintenance role "
            "could not be verified."
        )

    print("")
    print("MAINTENANCE ROLE SETUP: PASS")
    print(f"Role: {result[0]}")
    print(f"Superuser: {bool(result[1])}")
    print(f"CREATEDB: {bool(result[2])}")
    print(f"CREATEROLE: {bool(result[3])}")
    print(f"Replication: {bool(result[4])}")
    print(f"Bypass RLS: {bool(result[5])}")
    print(
        "The password was not written to the project."
    )


if __name__ == "__main__":
    main()
