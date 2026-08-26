from __future__ import annotations

import ast
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Phase8RecoveryContracts(unittest.TestCase):
    def test_phase8_never_grants_createdb_to_app_role(self):
        source = (
            PROJECT_ROOT
            / "services"
            / "recovery_validation_service.py"
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn(
            "ALTER ROLE mdrrmo_app CREATEDB",
            source,
        )
        self.assertNotIn(
            "GRANT CREATEDB",
            source,
        )

    def test_restore_runs_as_application_role(self):
        source = (
            PROJECT_ROOT
            / "services"
            / "recovery_validation_service.py"
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            '"--username",\n            parts["username"]',
            source,
        )
        self.assertIn(
            '"application_role_restore":\n                True',
            source,
        )

    def test_maintenance_password_is_prompted_not_cli_argument(self):
        source = (
            PROJECT_ROOT
            / "scripts"
            / "phase8_validation.py"
        ).read_text(
            encoding="utf-8-sig"
        )

        tree = ast.parse(source)
        argument_strings = []

        for node in ast.walk(tree):
            if not isinstance(
                node,
                ast.Call,
            ):
                continue

            if (
                isinstance(
                    node.func,
                    ast.Attribute,
                )
                and node.func.attr
                == "add_argument"
            ):
                for argument in node.args:
                    if isinstance(
                        argument,
                        ast.Constant,
                    ) and isinstance(
                        argument.value,
                        str,
                    ):
                        argument_strings.append(
                            argument.value
                        )

        self.assertNotIn(
            "--maintenance-password",
            argument_strings,
        )
        self.assertIn(
            "getpass(",
            source,
        )

    def test_phase8_evidence_is_git_safe(self):
        source = (
            PROJECT_ROOT
            / "services"
            / "recovery_validation_service.py"
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn(
            '"password":',
            source,
        )
        self.assertIn(
            "PHASE8_VALIDATION_RESULTS.json",
            source,
        )

    def test_setup_role_is_not_superuser(self):
        source = (
            PROJECT_ROOT
            / "scripts"
            / "setup_restore_maintenance_role.py"
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "CREATEDB",
            source,
        )
        self.assertIn(
            "NOSUPERUSER",
            source,
        )
        self.assertIn(
            "NOCREATEROLE",
            source,
        )


if __name__ == "__main__":
    unittest.main()
