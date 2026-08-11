from __future__ import annotations

from pathlib import Path
import unittest

from services.access_service import CurrentAppUser
from utils.auth import (
    CURRENT_APP_USER_EMAIL_SESSION_KEY,
    CURRENT_APP_USER_SESSION_KEY,
    _clear_current_app_user_state,
    _read_cached_current_app_user,
    _write_current_app_user_state,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AuthorizationSessionStateTests(
    unittest.TestCase
):
    def setUp(self):
        self.user = CurrentAppUser(
            id=42,
            email="authorized@example.test",
            display_name="Authorized Test User",
            role="Viewer",
            permissions=frozenset(
                {"view_dashboard"}
            ),
        )

    def test_session_cache_round_trip(self):
        state: dict[str, object] = {}

        _write_current_app_user_state(
            state,
            self.user,
        )

        result = _read_cached_current_app_user(
            state,
            email=self.user.email,
        )

        self.assertEqual(
            result,
            self.user,
        )

    def test_session_cache_rejects_other_identity(self):
        state: dict[str, object] = {}

        _write_current_app_user_state(
            state,
            self.user,
        )

        result = _read_cached_current_app_user(
            state,
            email="other@example.test",
        )

        self.assertIsNone(
            result
        )

    def test_session_cache_can_be_cleared(self):
        state: dict[str, object] = {
            CURRENT_APP_USER_SESSION_KEY:
                self.user,
            CURRENT_APP_USER_EMAIL_SESSION_KEY:
                self.user.email,
        }

        _clear_current_app_user_state(
            state
        )

        self.assertNotIn(
            CURRENT_APP_USER_SESSION_KEY,
            state,
        )
        self.assertNotIn(
            CURRENT_APP_USER_EMAIL_SESSION_KEY,
            state,
        )


class AuthorizationRerunContracts(
    unittest.TestCase
):
    def test_app_refreshes_authorization_before_page_run(self):
        source = (
            PROJECT_ROOT
            / "app.py"
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "get_current_app_user("
            "\n    refresh_authorization=True"
            "\n)",
            source,
        )

    def test_authorization_is_not_streamlit_data_cached(self):
        source = (
            PROJECT_ROOT
            / "utils"
            / "auth.py"
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn(
            "@st.cache_data",
            source,
        )
        self.assertNotIn(
            "@st.cache_resource",
            source,
        )

    def test_page_permission_gate_uses_same_rerun_user(self):
        source = (
            PROJECT_ROOT
            / "utils"
            / "auth.py"
        ).read_text(
            encoding="utf-8-sig"
        )

        start = source.index(
            "def require_permission("
        )
        end = source.index(
            "def require_any_permission(",
            start,
        )
        function_text = source[
            start:end
        ]

        self.assertIn(
            "user = get_current_app_user()",
            function_text,
        )
        self.assertNotIn(
            "refresh_authorization=True",
            function_text,
        )


if __name__ == "__main__":
    unittest.main()
