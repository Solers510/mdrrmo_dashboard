from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.backup_service import BackupServiceError, verify_backup_archive


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify a custom-format MDRRMO PostgreSQL backup."
    )
    parser.add_argument("backup", type=Path)
    args = parser.parse_args()

    metadata_path = args.backup.with_suffix(".json")
    expected_hash = None

    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        expected_hash = metadata.get("sha256")

    try:
        result = verify_backup_archive(
            args.backup,
            expected_sha256=expected_hash,
        )
    except BackupServiceError as error:
        raise SystemExit(f"BACKUP VERIFICATION FAILED: {error}")

    print("BACKUP VERIFICATION: PASS")
    print(f"File: {result['backup_path']}")
    print(f"SHA-256: {result['sha256']}")
    print(f"Size: {result['size_bytes']} bytes")


if __name__ == "__main__":
    main()
