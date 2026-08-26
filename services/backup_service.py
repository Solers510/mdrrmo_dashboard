from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from database.connection import DATABASE_URL, engine

MANILA_TIMEZONE = ZoneInfo("Asia/Manila")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_DIRECTORY = PROJECT_ROOT / "backups"


class BackupServiceError(Exception):
    """Raised when PostgreSQL backup or verification fails."""


def _common_postgresql_bins(tool_name: str) -> list[Path]:
    candidates: list[Path] = []

    for environment_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.getenv(environment_name)
        if not base:
            continue

        postgres_root = Path(base) / "PostgreSQL"
        if not postgres_root.exists():
            continue

        version_directories = sorted(
            (path for path in postgres_root.iterdir() if path.is_dir()),
            reverse=True,
        )

        for version_directory in version_directories:
            candidate = version_directory / "bin" / f"{tool_name}.exe"
            if candidate.exists():
                candidates.append(candidate)

    return candidates


def find_postgresql_tool(tool_name: str) -> Path | None:
    discovered = shutil.which(tool_name)
    if discovered:
        return Path(discovered)

    common = _common_postgresql_bins(tool_name)
    return common[0] if common else None


def database_connection_parts() -> dict[str, Any]:
    if not DATABASE_URL:
        raise BackupServiceError("DATABASE_URL is not configured.")

    url = make_url(DATABASE_URL)

    if not url.drivername.startswith("postgresql"):
        raise BackupServiceError("Backup tools support PostgreSQL only.")

    if not url.username or not url.database:
        raise BackupServiceError(
            "DATABASE_URL is missing the PostgreSQL user or database name."
        )

    return {
        "host": url.host or "localhost",
        "port": int(url.port or 5432),
        "username": str(url.username),
        "password": str(url.password) if url.password is not None else "",
        "database": str(url.database),
    }


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _public_table_counts() -> dict[str, int]:
    inspector = inspect(engine)
    table_names = sorted(inspector.get_table_names(schema="public"))
    preparer = engine.dialect.identifier_preparer
    counts: dict[str, int] = {}

    with engine.connect() as connection:
        for table_name in table_names:
            quoted = preparer.quote(table_name)
            counts[table_name] = int(
                connection.execute(
                    text(f"SELECT COUNT(*) FROM {quoted}")
                ).scalar_one()
            )

    return counts


def _alembic_revision() -> str | None:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).first()
    return str(row[0]) if row else None


def verify_backup_archive(
    backup_path: Path,
    *,
    expected_sha256: str | None = None,
) -> dict[str, object]:
    backup_path = backup_path.resolve()

    if not backup_path.is_file():
        raise BackupServiceError("The backup file does not exist.")

    digest = sha256_file(backup_path)
    if expected_sha256 is not None and digest.lower() != expected_sha256.lower():
        raise BackupServiceError("The backup SHA-256 checksum does not match.")

    pg_restore = find_postgresql_tool("pg_restore")
    if pg_restore is None:
        raise BackupServiceError(
            "pg_restore was not found. Install PostgreSQL client tools "
            "or add PostgreSQL bin to PATH."
        )

    result = subprocess.run(
        [str(pg_restore), "--list", str(backup_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise BackupServiceError("pg_restore could not read the backup archive.")

    listing = result.stdout
    expected_markers = (
        "TABLE public disaster_events",
        "TABLE public barangay_updates",
        "TABLE public evacuation_center_updates",
        "TABLE public app_users",
        "TABLE public report_snapshots",
        "TABLE public system_audit_log",
    )
    missing = [marker for marker in expected_markers if marker not in listing]
    if missing:
        raise BackupServiceError(
            "The archive is readable but is missing expected database objects: "
            + ", ".join(missing)
        )

    return {
        "backup_path": str(backup_path),
        "sha256": digest,
        "size_bytes": backup_path.stat().st_size,
        "pg_restore": str(pg_restore),
        "archive_readable": True,
    }


def create_database_backup(
    *,
    backup_directory: Path | None = None,
) -> dict[str, object]:
    pg_dump = find_postgresql_tool("pg_dump")
    if pg_dump is None:
        raise BackupServiceError(
            "pg_dump was not found. Install PostgreSQL client tools "
            "or add PostgreSQL bin to PATH."
        )

    connection = database_connection_parts()
    output_directory = (
        backup_directory if backup_directory is not None else DEFAULT_BACKUP_DIRECTORY
    ).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(MANILA_TIMEZONE).strftime("%Y%m%d-%H%M%S")
    backup_path = output_directory / f"mdrrmo_dashboard_{timestamp}.backup"

    environment = os.environ.copy()
    environment["PGPASSWORD"] = connection["password"]

    command = [
        str(pg_dump),
        "--host", connection["host"],
        "--port", str(connection["port"]),
        "--username", connection["username"],
        "--dbname", connection["database"],
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--file", str(backup_path),
    ]

    result = subprocess.run(
        command,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        if backup_path.exists():
            backup_path.unlink()
        raise BackupServiceError(
            "pg_dump failed. The database password and connection URL were "
            "not printed. Review PostgreSQL availability and permissions."
        )

    digest = sha256_file(backup_path)
    verification = verify_backup_archive(
        backup_path,
        expected_sha256=digest,
    )

    metadata = {
        "created_at": datetime.now(MANILA_TIMEZONE).isoformat(),
        "database_name": connection["database"],
        "alembic_revision": _alembic_revision(),
        "sha256": digest,
        "size_bytes": backup_path.stat().st_size,
        "table_counts": _public_table_counts(),
        "archive_verified": bool(verification["archive_readable"]),
    }

    metadata_path = backup_path.with_suffix(".json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    checksum_path = backup_path.with_suffix(".sha256")
    checksum_path.write_text(
        f"{digest}  {backup_path.name}\n",
        encoding="utf-8",
    )

    return {
        **metadata,
        "backup_path": str(backup_path),
        "metadata_path": str(metadata_path),
        "checksum_path": str(checksum_path),
        "pg_dump": str(pg_dump),
    }


def list_backups(
    *,
    backup_directory: Path | None = None,
) -> list[dict[str, object]]:
    directory = (
        backup_directory if backup_directory is not None else DEFAULT_BACKUP_DIRECTORY
    ).resolve()
    if not directory.exists():
        return []

    rows: list[dict[str, object]] = []
    for backup_path in sorted(
        directory.glob("*.backup"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ):
        metadata_path = backup_path.with_suffix(".json")
        metadata: dict[str, object] = {}

        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                metadata = {}

        rows.append(
            {
                "filename": backup_path.name,
                "path": str(backup_path),
                "size_bytes": backup_path.stat().st_size,
                "created_at": metadata.get("created_at"),
                "sha256": metadata.get("sha256"),
                "alembic_revision": metadata.get("alembic_revision"),
                "archive_verified": metadata.get("archive_verified"),
            }
        )

    return rows
