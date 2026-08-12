from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "validation.py"


class ValidationWorkspaceContracts(unittest.TestCase):
    def test_operational_header_and_event_strip(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn("render_operational_page_header(", source)
        self.assertIn("render_operational_event_strip(", source)
        self.assertNotIn('st.title("Operational Report Validation")', source)

    def test_attention_first_workload(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('title="Validation Workload"', source)
        self.assertIn("render_attention_required(attention_items)", source)
        self.assertIn('f"Barangay Queue ({len(barangay_queue)})"', source)
        self.assertIn('f"EC Queue ({len(evacuation_queue)})"', source)

    def test_barangay_queue_is_compact(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('"Affected F / I"', source)
        self.assertIn('"Displaced"', source)
        self.assertIn('"Age": format_report_age(', source)

    def test_ec_queue_is_compact(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('"Occupancy F / I"', source)
        self.assertIn('"Food · Water · Power"', source)

    def test_reconciliation_is_problem_first_and_null_safe(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('title="Source Reconciliation"', source)
        self.assertIn("RECONCILIATION_ACTION_STATUSES", source)
        self.assertIn(
            'if row["reconciliation_status"]\n'
            '            in RECONCILIATION_ACTION_STATUSES',
            source,
        )
        self.assertIn(
            'if row["reconciliation_status"] == "No Current Data"',
            source,
        )
        self.assertIn("format_pair(", source)
        self.assertIn('"Full reconciliation source timestamps"', source)

    def test_reconciliation_count_and_primary_queue_share_semantics(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn(
            'f"Reconciliation ({reconciliation_action_count})"',
            source,
        )
        self.assertIn("They are excluded from the ", source)
        self.assertNotIn(
            'if row["reconciliation_status"] != "Match"',
            source,
        )

    def test_validation_kpi_grids_do_not_force_three_column_wrap(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertNotIn("compact=True", source)

    def test_review_semantics_are_preserved(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        required = (
            "get_barangay_validation_queue(",
            "get_evacuation_validation_queue(",
            "get_population_reconciliation_queue(",
            "review_barangay_update(",
            "review_evacuation_update(",
            'options=("Validated", "Needs Correction")',
            "reviewer_user_id=current_user.id",
            "review_notes=notes",
            "review_notes=ec_notes",
        )
        for token in required:
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
