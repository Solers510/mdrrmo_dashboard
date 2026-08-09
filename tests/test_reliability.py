import tempfile
import unittest
from pathlib import Path

from services.backup_service import sha256_file
from utils.error_handling import redact_sensitive_text


class ErrorRedactionTests(unittest.TestCase):
    def test_database_password_is_redacted(self):
        value = "postgresql+psycopg://mdrrmo:super-secret@localhost/db"
        redacted = redact_sensitive_text(value)
        self.assertNotIn("super-secret", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_named_secret_is_redacted(self):
        value = "client_secret=my-secret-value"
        redacted = redact_sensitive_text(value)
        self.assertNotIn("my-secret-value", redacted)


class BackupHashTests(unittest.TestCase):
    def test_sha256_file_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.backup"
            path.write_bytes(b"mdrrmo-backup-test")
            first = sha256_file(path)
            second = sha256_file(path)
            self.assertEqual(first, second)
            self.assertEqual(len(first), 64)


class ProductionErrorDisplayTests(unittest.TestCase):
    def test_pages_do_not_render_raw_streamlit_exceptions(self):
        project_root = Path(__file__).resolve().parents[1]
        offenders = []
        for path in (project_root / "pages").glob("*.py"):
            source = path.read_text(encoding="utf-8-sig")
            if "st.exception(" in source:
                offenders.append(path.name)

        self.assertEqual(
            offenders,
            [],
            msg="Raw Streamlit exception rendering remains in: "
            + ", ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
