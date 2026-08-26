from __future__ import annotations

import argparse
from pathlib import Path

from services.backup_service import BackupServiceError, create_database_backup


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create and verify a PostgreSQL MDRRMO backup."
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=None,
        help="Optional backup output directory.",
    )
    args = parser.parse_args()

    try:
        result = create_database_backup(backup_directory=args.directory)
    except BackupServiceError as error:
        raise SystemExit(f"BACKUP FAILED: {error}")

    print("BACKUP: PASS")
    print(f"File: {result['backup_path']}")
    print(f"Size: {result['size_bytes']} bytes")
    print(f"SHA-256: {result['sha256']}")
    print(f"Alembic revision: {result['alembic_revision']}")
    print("Archive verification: PASS")


if __name__ == "__main__":
    main()
