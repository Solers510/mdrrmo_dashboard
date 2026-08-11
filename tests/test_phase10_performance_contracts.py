from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

from scripts.phase10_performance_baseline import (
    normalize_sql,
    sql_fingerprint,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Phase10PerformanceContracts(
    unittest.TestCase
):
    def test_sql_normalization_removes_literals(
        self,
    ):
        source = (
            "SELECT * FROM example "
            "WHERE id = 42 "
            "AND name = 'Sensitive Name'"
        )
        normalized = normalize_sql(
            source
        )

        self.assertNotIn(
            "42",
            normalized,
        )
        self.assertNotIn(
            "Sensitive Name",
            normalized,
        )

    def test_sql_fingerprint_is_stable(
        self,
    ):
        first = sql_fingerprint(
            normalize_sql(
                "SELECT  * FROM x WHERE id = 1"
            )
        )
        second = sql_fingerprint(
            normalize_sql(
                "SELECT * FROM x WHERE id = 99"
            )
        )
        self.assertEqual(
            first,
            second,
        )

    def test_performance_results_are_ignored(
        self,
    ):
        gitignore = (
            PROJECT_ROOT
            / ".gitignore"
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "performance_results/",
            gitignore,
        )

    def test_performance_results_are_not_tracked(
        self,
    ):
        output = subprocess.check_output(
            [
                "git",
                "ls-files",
                "performance_results",
            ],
            cwd=PROJECT_ROOT,
            text=True,
        )
        self.assertEqual(
            output.strip(),
            "",
        )


if __name__ == "__main__":
    unittest.main()
