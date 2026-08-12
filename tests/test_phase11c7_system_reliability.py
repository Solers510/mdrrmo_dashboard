from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "system_admin.py"


class SystemReliabilityWorkspaceContracts(unittest.TestCase):
    def test_page_runtime_smoke_with_current_reliability_data(self):
        now = datetime(2026, 8, 12, tzinfo=timezone.utc)
        current_user = SimpleNamespace(
            id=1,
            email="admin@example.com",
            display_name="Administrator",
            role="Administrator",
        )
        health_rows = [
            {
                "check": "PostgreSQL connectivity",
                "status": "PASS",
                "detail": "Database connection succeeded.",
            },
            {
                "check": "Backup retention",
                "status": "WARN",
                "detail": "Off-site retention requires confirmation.",
            },
        ]
        audit_rows = [
            {
                "id": 7,
                "table_name": "app_users",
                "operation": "UPDATE",
                "record_id": "2",
                "actor_snapshot": "Administrator",
                "old_data": {"role": "Encoder"},
                "new_data": {"role": "Validator"},
                "occurred_at": now,
            }
        ]
        backup_rows = [
            {
                "filename": "mdrrmo_dashboard_20260812-090000.backup",
                "path": "C:/backups/mdrrmo_dashboard_20260812-090000.backup",
                "size_bytes": 125000,
                "created_at": now.isoformat(),
                "sha256": "a" * 64,
                "alembic_revision": "f5a8d3c74211",
                "archive_verified": True,
            }
        ]

        with (
            patch(
                "utils.auth.require_permission",
                return_value=current_user,
            ),
            patch(
                "services.system_health_service.run_system_health_checks",
                return_value=health_rows,
            ),
            patch(
                "services.audit_service.list_audit_entries",
                return_value=audit_rows,
            ),
            patch(
                "services.backup_service.list_backups",
                return_value=backup_rows,
            ),
        ):
            app = AppTest.from_file(str(PAGE)).run(timeout=10)

        self.assertEqual(list(app.exception), [])

    def test_operational_header_and_command_picture(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('title="System Reliability & Audit"', source)
        self.assertIn('title="Reliability Command Picture"', source)
        self.assertNotIn('st.title("System Health, Audit and Recovery")', source)
        for token in (
            '"System Status"',
            '"Failed Checks"',
            '"Audit Entries Loaded"',
            '"Verified Backups"',
            '"Latest Backup"',
            '"Off-Machine Backup Retention"',
            '"Manual Verification"',
        ):
            self.assertIn(token, source)

    def test_health_workspace_prioritizes_exceptions(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            'title="System Health Checks"',
            "HEALTH_STATUS_ORDER",
            '"Failed Health Checks"',
            '"Health Warnings"',
            '"Readiness Detail"',
            "run_system_health_checks()",
            "overall_health_status(health_rows)",
        ):
            self.assertIn(token, source)

    def test_audit_workspace_remains_append_only_and_inspectable(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            'title="Immutable System Audit Trail"',
            "list_audit_entries(limit=500)",
            '"Inspect exact audit entry"',
            '"### Previous Row State"',
            '"### New Row State"',
            "selected[\"old_data\"]",
            "selected[\"new_data\"]",
            "audit_data_area_label(",
            "ensure_ascii=False",
            "no edit or delete ",
            "action for audit records.",
        ):
            self.assertIn(token, source)

    def test_backup_creation_preserves_verified_service_semantics(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            'title="Verified Backup & Recovery"',
            'title="Confirm Backup Context"',
            'title="Authorize Local Archive Creation"',
            "create_database_backup()",
            "BackupServiceError",
            "disabled=not backup_confirmation",
            '"SHA-256 integrity hash"',
            '"Local archive path"',
            '"Archive Reference"',
            "archive_reference(",
        ):
            self.assertIn(token, source)

        self.assertNotIn('"Latest Size"', source)

    def test_restore_stays_terminal_only_and_disposable(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            'title="Controlled Restore Drill"',
            'title="Keep PostgreSQL Running"',
            'title="Run the Latest Verified Archive"',
            'title="Preserve Recovery Evidence"',
            "python scripts/restore_test.py --latest",
            "disposable database",
            "intentionally unavailable as an in-app",
        ):
            self.assertIn(token, source)

    def test_administrator_permission_gate_remains(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn(
            "current_user = require_permission(PERMISSION_MANAGE_USERS)",
            source,
        )


if __name__ == "__main__":
    unittest.main()
