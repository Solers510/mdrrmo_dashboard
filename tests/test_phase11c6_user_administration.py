from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "user_admin.py"


class UserAdministrationWorkspaceContracts(unittest.TestCase):
    def test_page_runtime_smoke_with_current_accounts(self):
        now = datetime(2026, 8, 12, tzinfo=timezone.utc)
        current_user = SimpleNamespace(
            id=1,
            email="admin@example.com",
            display_name="Administrator",
            role="Administrator",
        )
        users = [
            {
                "id": 1,
                "email": "admin@example.com",
                "display_name": "Administrator",
                "role": "Administrator",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 2,
                "email": "encoder@example.com",
                "display_name": "Encoder",
                "role": "Encoder",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        ]

        with (
            patch(
                "utils.auth.require_permission",
                return_value=current_user,
            ),
            patch(
                "services.user_admin_service.list_app_users",
                return_value=users,
            ),
        ):
            app = AppTest.from_file(str(PAGE)).run(
                timeout=10
            )

        self.assertEqual(list(app.exception), [])

    def test_operational_header_and_access_picture(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn(
            'title="User Access Administration"',
            source,
        )
        self.assertIn('title="Access Control Picture"', source)
        self.assertNotIn('st.title("User Administration")', source)
        for label in (
            '"Authorized Accounts"',
            '"Active Accounts"',
            '"Inactive Accounts"',
            '"Active Administrators"',
        ):
            self.assertIn(label, source)

    def test_workspace_separates_directory_authorization_and_management(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            '"Account Directory (',
            '"Authorize Account"',
            '"Manage Account"',
            '"Role Guide"',
            'title="Authorized Account Directory"',
            'title="Authorize New Account"',
            'title="Manage Authorized Account"',
            'title="Application Role Guide"',
        ):
            self.assertIn(token, source)

    def test_new_account_workflow_preserves_service_semantics(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            'title="Confirm Identity"',
            'title="Assign Application Role"',
            'title="Review & Authorize"',
            "create_app_user(",
            "actor_user_id=current_user.id",
            "disabled=not confirmation",
            "UserAdminValidationError",
            "UserAdminPermissionError",
            "UserAdminIntegrityError",
        ):
            self.assertIn(token, source)

    def test_account_management_surfaces_but_does_not_replace_safeguards(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            "is_current_account = (",
            "is_final_active_administrator = (",
            "role_and_status_locked = (",
            "sensitive_change = (",
            "update_app_user(",
            "disabled=role_and_status_locked",
            "not change_pending",
        ):
            self.assertIn(token, source)

    def test_directory_and_role_guide_are_operationally_readable(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            '"OIDC Email"',
            '"Updated"',
            '"Current User"',
            "ROLE_PERMISSIONS",
            "role_access_summary(",
            '"Operational Purpose"',
            '"Inspect exact role permissions"',
            '"Granted Capability"',
            '"Permissions"',
        ):
            self.assertIn(token, source)

        self.assertNotIn('"Granted Capabilities"', source)

    def test_administrator_continuity_message_is_unambiguous(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('"No Backup Administrator"', source)
        self.assertIn('"1 Active Administrator"', source)
        self.assertNotIn('"Single Active Account"', source)

    def test_account_mutations_keep_actor_audit_identity(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertGreaterEqual(
            source.count("actor_user_id=current_user.id"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
