from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = (
    PROJECT_ROOT
    / "scripts"
    / "phase10d_optimization_closure_audit.py"
)
REPORT_PAGE = (
    PROJECT_ROOT
    / "pages"
    / "reports.py"
)


class Phase10DClosureAuditContracts(
    unittest.TestCase
):
    def test_audit_is_read_only(self):
        source = AUDIT_SCRIPT.read_text(
            encoding="utf-8-sig"
        )

        forbidden = (
            "session.add(",
            "session.delete(",
            "session.commit(",
            "session.flush(",
            "create_report_snapshot(",
        )

        for token in forbidden:
            self.assertNotIn(
                token,
                source,
            )

    def test_report_export_builders_are_currently_eager(self):
        source = REPORT_PAGE.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "build_excel_report(",
            source,
        )
        self.assertIn(
            "build_pdf_report(",
            source,
        )

    def test_audit_result_directory_is_ignored(self):
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


if __name__ == "__main__":
    unittest.main()
