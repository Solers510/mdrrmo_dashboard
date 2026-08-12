from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAGE_PATH = (
    PROJECT_ROOT
    / "pages"
    / "barangay_updates.py"
)
UI_PATH = (
    PROJECT_ROOT
    / "utils"
    / "ui.py"
)
CSS_PATH = (
    PROJECT_ROOT
    / "styles"
    / "mdrrmo.css"
)


class BarangayEncoderWorkflowContracts(
    unittest.TestCase
):
    def test_page_uses_operational_header_and_event_strip(
        self,
    ):
        source = PAGE_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "render_operational_page_header(",
            source,
        )
        self.assertIn(
            "render_operational_event_strip(",
            source,
        )
        self.assertNotIn(
            'st.title("Barangay Situation Update")',
            source,
        )
        self.assertNotIn(
            "event_columns = st.columns(3)",
            source,
        )

    def test_form_has_ordered_six_step_workflow(
        self,
    ):
        source = PAGE_PATH.read_text(
            encoding="utf-8-sig"
        )

        markers = (
            'step=1,\n    title="Select Barangay"',
            'step=2,\n    title="Inside Evacuation Centers"',
            'step=3,\n    title="Affected Population"',
            'step=4,\n    title="Outside Evacuation Centers"',
            'step=5,\n    title="Operational Conditions"',
            'step=6,\n    title="Source & Submit"',
        )

        positions = [
            source.index(marker)
            for marker in markers
        ]

        self.assertEqual(
            positions,
            sorted(positions),
        )

    def test_reference_and_reconciliation_use_shared_kpi_grid(
        self,
    ):
        source = PAGE_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertGreaterEqual(
            source.count(
                "render_kpi_grid("
            ),
            2,
        )
        self.assertNotIn(
            "reference_columns = st.columns(3)",
            source,
        )
        self.assertNotIn(
            "reconciliation_columns =",
            source,
        )

    def test_existing_submission_and_correction_semantics_remain(
        self,
    ):
        source = PAGE_PATH.read_text(
            encoding="utf-8-sig"
        )

        for token in (
            "create_barangay_update(",
            "get_pending_barangay_correction(",
            "supersede",
            "DuplicateBarangaySubmissionError",
            "reconcile_population(",
            "validate_flood_consistency(",
        ):
            self.assertIn(
                token,
                source,
            )

    def test_shared_workflow_component_escapes_dynamic_text(
        self,
    ):
        source = UI_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "def render_workflow_section(",
            source,
        )
        self.assertIn(
            "{escape(title)}",
            source,
        )
        self.assertIn(
            "{escape(subtitle)}",
            source,
        )

    def test_workflow_css_uses_public_application_classes_only(
        self,
    ):
        source = CSS_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            ".mdrrmo-workflow-section",
            source,
        )
        self.assertNotIn(
            "[data-testid=",
            source,
        )


class BarangayEncoderPolishContracts(
    unittest.TestCase
):
    def test_entry_labels_use_short_ec_wording(
        self,
    ):
        source = PAGE_PATH.read_text(
            encoding="utf-8-sig"
        )

        for label in (
            '"Families inside EC"',
            '"Individuals inside EC"',
            '"Families outside EC"',
            '"Individuals outside EC"',
        ):
            self.assertIn(
                label,
                source,
            )

    def test_recent_reports_use_compact_routine_table(
        self,
    ):
        source = PAGE_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            '"Affected F / I"',
            source,
        )
        self.assertIn(
            '"Displaced Individuals"',
            source,
        )
        self.assertIn(
            '"Age": format_report_age(',
            source,
        )
        self.assertIn(
            'pinned=True',
            source,
        )

    def test_full_recent_report_fields_remain_available(
        self,
    ):
        source = PAGE_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            '"Full recent report fields"',
            source,
        )
        self.assertIn(
            '"Source": row[',
            source,
        )
        self.assertIn(
            '"Recorded At": row[',
            source,
        )

    def test_compact_report_age_uses_operational_notation(
        self,
    ):
        source = PAGE_PATH.read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "def format_report_age(",
            source,
        )
        self.assertIn(
            'return "<1m"',
            source,
        )
        self.assertIn(
            'return f"{minutes}m"',
            source,
        )
        self.assertIn(
            'return f"{hours}h"',
            source,
        )
        self.assertIn(
            'return f"{hours // 24}d"',
            source,
        )


if __name__ == "__main__":
    unittest.main()
