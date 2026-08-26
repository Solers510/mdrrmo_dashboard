from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from config.runtime import (
    bounded_integer,
    deployment_mode,
    is_cloud_deployment,
    normalize_database_url,
)


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "system_admin.py"


class RuntimeProfileContracts(unittest.TestCase):
    def test_local_profile_is_safe_default(self):
        self.assertEqual(deployment_mode({}), "local")
        self.assertFalse(is_cloud_deployment({}))

    def test_cloud_profile_is_explicit(self):
        environment = {"APP_DEPLOYMENT_MODE": "CLOUD"}
        self.assertEqual(deployment_mode(environment), "cloud")
        self.assertTrue(is_cloud_deployment(environment))

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(RuntimeError):
            deployment_mode({"APP_DEPLOYMENT_MODE": "production-ish"})

    def test_common_provider_url_uses_psycopg_three(self):
        self.assertEqual(
            normalize_database_url(
                "postgresql://user:password@example.test:5432/database"
            ),
            "postgresql+psycopg://user:password@example.test:5432/database",
        )
        self.assertEqual(
            normalize_database_url(
                "postgres://user:password@example.test:5432/database"
            ),
            "postgresql+psycopg://user:password@example.test:5432/database",
        )

    def test_bounded_integer_rejects_unsafe_values(self):
        self.assertEqual(
            bounded_integer(
                "DB_POOL_SIZE",
                4,
                minimum=1,
                maximum=8,
                environ={"DB_POOL_SIZE": "4"},
            ),
            4,
        )
        with self.assertRaises(RuntimeError):
            bounded_integer(
                "DB_POOL_SIZE",
                4,
                minimum=1,
                maximum=8,
                environ={"DB_POOL_SIZE": "20"},
            )


class CloudReliabilityWorkspaceContracts(unittest.TestCase):
    def test_cloud_page_runtime_avoids_local_backup_listing(self):
        now = datetime(2026, 8, 13, tzinfo=timezone.utc)
        current_user = SimpleNamespace(
            id=1,
            email="admin@example.com",
            display_name="Administrator",
            role="Administrator",
        )
        health_rows = [
            {
                "check": "Database transport encryption",
                "status": "PASS",
                "detail": "The active PostgreSQL connection uses TLS.",
            }
        ]
        audit_rows = [
            {
                "id": 1,
                "table_name": "app_users",
                "operation": "UPDATE",
                "record_id": "1",
                "actor_snapshot": "Administrator",
                "old_data": {"role": "Administrator"},
                "new_data": {"role": "Administrator"},
                "occurred_at": now,
            }
        ]

        with (
            patch(
                "utils.auth.require_permission",
                return_value=current_user,
            ),
            patch(
                "config.runtime.is_cloud_deployment",
                return_value=True,
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
                "services.backup_service.list_backups"
            ) as list_backups,
        ):
            app = AppTest.from_file(str(PAGE)).run(timeout=10)

        self.assertEqual(list(app.exception), [])
        list_backups.assert_not_called()

    def test_cloud_page_disables_ephemeral_backup_controls(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            "IS_CLOUD_DEPLOYMENT",
            'title="Cloud Backup & Recovery"',
            "Streamlit Community Cloud storage is temporary",
            'title="Verify Provider Recovery"',
            'title="Use a Trusted Backup Workstation"',
            'title="Use an Isolated PostgreSQL Target"',
            "never the live Aiven pilot database",
        ):
            self.assertIn(token, source)

    def test_cloud_secret_template_contains_placeholders_only(self):
        template = (
            ROOT / ".streamlit" / "secrets.cloud.example.toml"
        ).read_text(encoding="utf-8-sig")
        self.assertIn('APP_DEPLOYMENT_MODE = "cloud"', template)
        self.assertIn("REPLACE_AIVEN_HOST", template)
        self.assertIn("REPLACE_STREAMLIT_SUBDOMAIN", template)
        self.assertNotIn("localhost", template.lower())


class CloudDocumentationContracts(unittest.TestCase):
    def test_runbook_preserves_pilot_and_rollback_boundaries(self):
        source = (
            ROOT / "deployment" / "CLOUD_PILOT_RUNBOOK.md"
        ).read_text(encoding="utf-8-sig")
        for token in (
            "does not authorize production use",
            "Do not use simultaneous local and cloud writes",
            "live Aiven pilot database as the restore target",
            "independent encrypted archive",
            "Phase 11C7 remains the verified local rollback baseline",
        ):
            self.assertIn(token, source)

    def test_management_checklist_is_plain_language_and_secret_safe(self):
        source = (
            ROOT / "deployment" / "CLOUD_PILOT_DECISION_CHECKLIST.md"
        ).read_text(encoding="utf-8-sig")
        for token in (
            "Official service owner",
            "Approved pilot users and roles",
            "Classification of the present database",
            "Independent backup destination",
            "Cloud, privacy, and operating approval",
            "passwords, recovery codes",
        ):
            self.assertIn(token.lower(), source.lower())

    def test_offline_cloud_preflight_passes_with_manual_gates(self):
        result = subprocess.run(
            [sys.executable, "scripts/cloud_pilot_preflight.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("PASS WITH MANUAL GATES", result.stdout)


if __name__ == "__main__":
    unittest.main()
