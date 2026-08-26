import ast
from pathlib import Path
import subprocess
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory

from config.access_control import (
    ALL_PERMISSIONS,
    ROLE_ADMINISTRATOR,
    ROLE_ENCODER,
    ROLE_EXECUTIVE,
    ROLE_OPERATIONS_OFFICER,
    ROLE_PERMISSIONS,
    ROLE_VALIDATOR,
    ROLE_VIEWER,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_latest_ec_repository_function_is_unique(self):
        source = (
            PROJECT_ROOT
            / "database"
            / "repositories.py"
        ).read_text(
            encoding="utf-8-sig"
        )
        tree = ast.parse(source)

        target = (
            "fetch_latest_evacuation_updates_for_event"
        )

        matches = [
            node
            for node in tree.body
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == target
        ]

        self.assertEqual(
            len(matches),
            1,
            msg=(
                f"{target} must have exactly one "
                "top-level definition."
            ),
        )

    def test_repository_top_level_functions_are_unique(self):
        source = (
            PROJECT_ROOT
            / "database"
            / "repositories.py"
        ).read_text(
            encoding="utf-8-sig"
        )
        tree = ast.parse(source)
        names = [
            node.name
            for node in tree.body
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
        ]

        duplicates = sorted(
            {
                name
                for name in names
                if names.count(name) > 1
            }
        )

        self.assertEqual(
            duplicates,
            [],
            msg=(
                "Duplicate repository functions: "
                + ", ".join(
                    duplicates
                )
            ),
        )


class RoleContractTests(unittest.TestCase):
    def test_administrator_has_all_permissions(self):
        self.assertEqual(
            ROLE_PERMISSIONS[
                ROLE_ADMINISTRATOR
            ],
            ALL_PERMISSIONS,
        )

    def test_viewer_is_dashboard_only(self):
        self.assertEqual(
            ROLE_PERMISSIONS[
                ROLE_VIEWER
            ],
            frozenset(
                {
                    "view_dashboard",
                }
            ),
        )

    def test_executive_is_read_only_dashboard_and_reports(self):
        self.assertEqual(
            ROLE_PERMISSIONS[
                ROLE_EXECUTIVE
            ],
            frozenset(
                {
                    "view_dashboard",
                    "view_reports",
                }
            ),
        )

    def test_encoder_cannot_validate_or_manage_users(self):
        permissions = ROLE_PERMISSIONS[
            ROLE_ENCODER
        ]
        self.assertIn(
            "submit_barangay_updates",
            permissions,
        )
        self.assertIn(
            "submit_evacuation_updates",
            permissions,
        )
        self.assertNotIn(
            "validate_barangay_reports",
            permissions,
        )
        self.assertNotIn(
            "manage_users",
            permissions,
        )

    def test_validator_does_not_submit_operational_reports(self):
        permissions = ROLE_PERMISSIONS[
            ROLE_VALIDATOR
        ]
        self.assertIn(
            "validate_barangay_reports",
            permissions,
        )
        self.assertNotIn(
            "submit_barangay_updates",
            permissions,
        )
        self.assertNotIn(
            "submit_evacuation_updates",
            permissions,
        )

    def test_operations_officer_cannot_manage_users(self):
        permissions = ROLE_PERMISSIONS[
            ROLE_OPERATIONS_OFFICER
        ]
        self.assertNotIn(
            "manage_users",
            permissions,
        )


class SecurityContractTests(unittest.TestCase):
    def test_local_secret_files_are_not_tracked(self):
        result = subprocess.run(
            [
                "git",
                "ls-files",
                ".env",
                ".streamlit/secrets.toml",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertEqual(
            result.stdout.strip(),
            "",
        )

    def test_no_raw_streamlit_exception_rendering(self):
        offenders = []

        for path in (
            PROJECT_ROOT
            / "pages"
        ).glob("*.py"):
            source = path.read_text(
                encoding="utf-8-sig"
            )

            if "st.exception(" in source:
                offenders.append(
                    path.name
                )

        self.assertEqual(
            offenders,
            [],
        )


class MigrationContractTests(unittest.TestCase):
    def test_alembic_has_one_head(self):
        config = Config(
            str(
                PROJECT_ROOT
                / "alembic.ini"
            )
        )
        script_location = (
            config.get_main_option(
                "script_location"
            )
        )

        if not Path(
            script_location
        ).is_absolute():
            config.set_main_option(
                "script_location",
                str(
                    PROJECT_ROOT
                    / script_location
                ),
            )

        heads = ScriptDirectory.from_config(
            config
        ).get_heads()

        self.assertEqual(
            len(heads),
            1,
            msg=f"Alembic heads: {heads}",
        )


if __name__ == "__main__":
    unittest.main()
