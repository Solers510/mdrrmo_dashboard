import os
from pathlib import Path
import unittest
from unittest.mock import patch

from database.connection import (
    DB_CONNECT_TIMEOUT_SECONDS,
    DB_POOL_TIMEOUT_SECONDS,
    ENGINE_OPTIONS,
)
from utils.app_logging import get_app_log_path, sanitize_log_text

class DatabaseTimeoutConfigurationTests(unittest.TestCase):
    def test_connect_timeout_enabled(self):
        self.assertGreaterEqual(DB_CONNECT_TIMEOUT_SECONDS, 1)
        self.assertLessEqual(DB_CONNECT_TIMEOUT_SECONDS, 10)
        self.assertEqual(
            ENGINE_OPTIONS["connect_args"]["connect_timeout"],
            DB_CONNECT_TIMEOUT_SECONDS,
        )

    def test_pool_timeout_enabled(self):
        self.assertGreaterEqual(DB_POOL_TIMEOUT_SECONDS, 1)
        self.assertLessEqual(DB_POOL_TIMEOUT_SECONDS, 10)
        self.assertEqual(
            ENGINE_OPTIONS["pool_timeout"],
            DB_POOL_TIMEOUT_SECONDS,
        )

    def test_pool_pre_ping_enabled(self):
        self.assertTrue(ENGINE_OPTIONS["pool_pre_ping"])

class LogRedactionTests(unittest.TestCase):
    def test_environment_secret_is_redacted(self):
        with patch.dict(
            os.environ,
            {"TEST_DATABASE_PASSWORD": "super-secret-value-123"},
            clear=False,
        ):
            result = sanitize_log_text("Failure super-secret-value-123")
        self.assertNotIn("super-secret-value-123", result)
        self.assertIn("[REDACTED]", result)

    def test_password_assignment_is_redacted(self):
        result = sanitize_log_text("password=my-db-password host=localhost")
        self.assertNotIn("my-db-password", result)
        self.assertIn("password=[REDACTED]", result)

    def test_database_url_password_is_redacted(self):
        result = sanitize_log_text(
            "postgresql+psycopg://user:secretpw@localhost/db"
        )
        self.assertNotIn("secretpw", result)
        self.assertIn("[REDACTED]", result)

    def test_log_path_is_project_logs(self):
        path = get_app_log_path()
        self.assertEqual(path.name, "mdrrmo_app.log")
        self.assertEqual(path.parent.name, "logs")

class AuthorizationFailureLoggingContractTests(unittest.TestCase):
    def test_auth_logs_access_service_failure(self):
        source = (
            Path(__file__).resolve().parents[1] / "utils" / "auth.py"
        ).read_text(encoding="utf-8-sig")
        self.assertIn('get_app_logger("auth")', source)
        self.assertIn("logger.exception(", source)
        self.assertIn(
            "The application could not verify your authorization.",
            source,
        )

if __name__ == "__main__":
    unittest.main()
