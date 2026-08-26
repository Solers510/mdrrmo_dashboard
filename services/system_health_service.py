from __future__ import annotations

from pathlib import Path
import tempfile

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from config.runtime import bounded_integer, is_cloud_deployment
from database.connection import engine
from services.backup_service import DEFAULT_BACKUP_DIRECTORY, find_postgresql_tool
from utils.error_handling import LOG_DIRECTORY

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"check": name, "status": status, "detail": detail}


def _directory_writable(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path,
        prefix="health_",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary_path = Path(handle.name)
    temporary_path.unlink(missing_ok=True)
    return True


def _cloud_database_checks() -> list[dict[str, str]]:
    results: list[dict[str, str]] = [
        _check(
            "Cloud deployment profile",
            "PASS",
            "Cloud safeguards are enabled; local archive controls are disabled.",
        )
    ]

    connection_limit = bounded_integer(
        "CLOUD_DATABASE_CONNECTION_LIMIT",
        20,
        minimum=5,
        maximum=500,
    )
    storage_limit_mb = bounded_integer(
        "CLOUD_DATABASE_STORAGE_LIMIT_MB",
        1024,
        minimum=128,
        maximum=1_000_000,
    )

    try:
        with engine.connect() as connection:
            transport_encrypted = bool(
                connection.execute(
                    text(
                        "SELECT COALESCE((SELECT ssl FROM pg_stat_ssl "
                        "WHERE pid = pg_backend_pid()), false)"
                    )
                ).scalar_one()
            )
        results.append(
            _check(
                "Database transport encryption",
                "PASS" if transport_encrypted else "FAIL",
                "The active PostgreSQL connection uses TLS."
                if transport_encrypted
                else "The active PostgreSQL connection is not encrypted.",
            )
        )
    except Exception as error:
        results.append(
            _check(
                "Database transport encryption",
                "FAIL",
                f"TLS verification failed: {type(error).__name__}.",
            )
        )

    try:
        with engine.connect() as connection:
            active_connections = int(
                connection.execute(
                    text(
                        "SELECT COUNT(*) FROM pg_stat_activity "
                        "WHERE datname = current_database()"
                    )
                ).scalar_one()
            )
        connection_percent = active_connections / connection_limit * 100
        results.append(
            _check(
                "Cloud database connection budget",
                "WARN" if connection_percent >= 75 else "PASS",
                f"{active_connections} of {connection_limit} configured "
                "connections are currently in use.",
            )
        )
    except Exception as error:
        results.append(
            _check(
                "Cloud database connection budget",
                "WARN",
                "Connection utilization could not be inspected: "
                f"{type(error).__name__}.",
            )
        )

    try:
        with engine.connect() as connection:
            database_size_bytes = int(
                connection.execute(
                    text("SELECT pg_database_size(current_database())")
                ).scalar_one()
            )
        database_size_mb = database_size_bytes / (1024 * 1024)
        storage_percent = database_size_mb / storage_limit_mb * 100
        results.append(
            _check(
                "Cloud database storage budget",
                "WARN" if storage_percent >= 75 else "PASS",
                f"{database_size_mb:.1f} MB of the configured "
                f"{storage_limit_mb} MB budget is in use.",
            )
        )
    except Exception as error:
        results.append(
            _check(
                "Cloud database storage budget",
                "WARN",
                "Database size could not be inspected: "
                f"{type(error).__name__}.",
            )
        )

    try:
        _directory_writable(LOG_DIRECTORY)
        results.append(
            _check(
                "Cloud runtime storage boundary",
                "PASS",
                "Runtime logs are writable but temporary. Database backups "
                "must be retained outside Streamlit Community Cloud.",
            )
        )
    except Exception as error:
        results.append(
            _check(
                "Cloud runtime storage boundary",
                "WARN",
                f"Runtime log storage is not writable: {type(error).__name__}.",
            )
        )

    return results


def run_system_health_checks() -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
            results.append(
                _check(
                    "PostgreSQL connectivity",
                    "PASS",
                    "Database connection succeeded.",
                )
            )

            active_events = int(
                connection.execute(
                    text(
                        "SELECT COUNT(*) FROM disaster_events "
                        "WHERE is_active = true"
                    )
                ).scalar_one()
            )
            results.append(
                _check(
                    "Active event integrity",
                    "PASS" if active_events <= 1 else "FAIL",
                    f"{active_events} active event(s).",
                )
            )

            active_admins = int(
                connection.execute(
                    text(
                        "SELECT COUNT(*) FROM app_users "
                        "WHERE is_active = true "
                        "AND role = 'Administrator'"
                    )
                ).scalar_one()
            )
            results.append(
                _check(
                    "Administrator availability",
                    "PASS" if active_admins >= 1 else "FAIL",
                    f"{active_admins} active Administrator account(s).",
                )
            )

            active_barangays = int(
                connection.execute(
                    text(
                        "SELECT COUNT(*) FROM barangays "
                        "WHERE is_active = true"
                    )
                ).scalar_one()
            )
            results.append(
                _check(
                    "Barangay master data",
                    "PASS" if active_barangays > 0 else "FAIL",
                    f"{active_barangays} active barangay record(s). "
                    "Authoritative names/count still require office verification.",
                )
            )

            for check_name, trigger_name in (
                (
                    "SitRep snapshot immutability",
                    "trg_report_snapshots_immutable",
                ),
                (
                    "Audit-log immutability",
                    "trg_system_audit_log_immutable",
                ),
            ):
                exists = bool(
                    connection.execute(
                        text(
                            """
                            SELECT EXISTS (
                                SELECT 1 FROM pg_trigger
                                WHERE tgname = :trigger_name
                                  AND NOT tgisinternal
                            )
                            """
                        ),
                        {"trigger_name": trigger_name},
                    ).scalar_one()
                )
                results.append(
                    _check(
                        check_name,
                        "PASS" if exists else "FAIL",
                        f"Trigger {trigger_name} is installed."
                        if exists
                        else f"Trigger {trigger_name} is missing.",
                    )
                )

            database_timezone = str(
                connection.execute(text("SHOW TIMEZONE")).scalar_one()
            )
            results.append(
                _check(
                    "Database timezone",
                    "PASS",
                    f"PostgreSQL timezone: {database_timezone}. "
                    "Operational display timestamps use Asia/Manila.",
                )
            )

    except Exception as error:
        results.append(
            _check(
                "PostgreSQL connectivity",
                "FAIL",
                f"Database health query failed: {type(error).__name__}.",
            )
        )
        return results

    try:
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        script_location = config.get_main_option("script_location")
        if not Path(script_location).is_absolute():
            config.set_main_option(
                "script_location",
                str(PROJECT_ROOT / script_location),
            )
        expected_head = ScriptDirectory.from_config(config).get_current_head()

        with engine.connect() as connection:
            current_revision = connection.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar_one_or_none()

        results.append(
            _check(
                "Alembic schema revision",
                "PASS" if current_revision == expected_head else "FAIL",
                f"Database={current_revision}; code={expected_head}.",
            )
        )
    except Exception as error:
        results.append(
            _check(
                "Alembic schema revision",
                "FAIL",
                f"Revision check failed: {type(error).__name__}.",
            )
        )

    try:
        tables = set(inspect(engine).get_table_names(schema="public"))
        required_tables = {
            "disaster_events",
            "barangay_updates",
            "evacuation_center_updates",
            "app_users",
            "report_snapshots",
            "system_audit_log",
        }
        missing_tables = sorted(required_tables - tables)
        results.append(
            _check(
                "Required database tables",
                "PASS" if not missing_tables else "FAIL",
                "All required tables are present."
                if not missing_tables
                else "Missing: " + ", ".join(missing_tables),
            )
        )
    except Exception as error:
        results.append(
            _check(
                "Required database tables",
                "FAIL",
                f"Table inspection failed: {type(error).__name__}.",
            )
        )

    if is_cloud_deployment():
        results.extend(_cloud_database_checks())
    else:
        pg_dump = find_postgresql_tool("pg_dump")
        pg_restore = find_postgresql_tool("pg_restore")
        results.append(
            _check(
                "PostgreSQL backup tools",
                "PASS" if pg_dump and pg_restore else "FAIL",
                (
                    f"pg_dump={pg_dump}; pg_restore={pg_restore}."
                    if pg_dump and pg_restore
                    else "pg_dump and/or pg_restore could not be found."
                ),
            )
        )

        for name, directory in (
            ("Backup directory", DEFAULT_BACKUP_DIRECTORY),
            ("Application log directory", LOG_DIRECTORY),
        ):
            try:
                _directory_writable(directory)
                results.append(
                    _check(name, "PASS", f"Writable: {directory}")
                )
            except Exception as error:
                results.append(
                    _check(
                        name,
                        "FAIL",
                        f"Not writable: {type(error).__name__}.",
                    )
                )

    return results


def overall_health_status(results: list[dict[str, str]]) -> str:
    statuses = {row["status"] for row in results}
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"
