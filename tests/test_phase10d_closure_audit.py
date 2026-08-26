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

    def test_audit_tracks_report_export_rerun_behavior(self):
        source = AUDIT_SCRIPT.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "excel_build_calls_in_page",
            source,
        )
        self.assertIn(
            "pdf_build_calls_in_page",
            source,
        )
        self.assertIn(
            "exports_built_during_normal_rerun",
            source,
        )
        self.assertIn(
            "@st.cache_data",
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
