from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "evacuation_centers.py"


class EvacuationWorkflowContracts(unittest.TestCase):
    def test_header_and_event_strip(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn("render_operational_page_header(", source)
        self.assertIn("render_operational_event_strip(", source)
        self.assertNotIn('st.title("Evacuation Center Monitoring")', source)

    def test_occupancy_update_is_primary_tab(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn(
            "update_tab, manage_tab, cross_tab, history_tab = st.tabs(",
            source,
        )
        self.assertLess(source.index('"Occupancy Update"'), source.index('"Center Registry'))

    def test_five_step_workflow(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for title in (
            "Select Evacuation Center",
            "Status & Occupancy",
            "Vulnerable Groups",
            "Essential Services",
            "Source & Submit",
        ):
            self.assertIn(title, source)

    def test_existing_semantics_remain(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            "get_pending_evacuation_correction(",
            "create_evacuation_center_update(",
            "create_cross_barangay_allocation(",
            "evacuation_submission_state_key",
            "correction_id",
            "EvacuationDataIntegrityError",
        ):
            self.assertIn(token, source)

    def test_recent_reports_are_compact_and_keep_full_source(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('"Occupancy F / I"', source)
        self.assertIn('"Food · Water · Power"', source)
        self.assertIn('"Age": format_report_age(', source)
        self.assertIn('"Full recent report fields"', source)
        self.assertIn('"Source": update["source"]', source)
        self.assertIn('"Recorded At": update["recorded_at"]', source)


class EvacuationVisualPolishContracts(unittest.TestCase):
    def test_cross_barangay_context_uses_compact_kpis(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('"label": "Latest EC Families"', source)
        self.assertIn('"label": "Foreign Origins"', source)
        self.assertNotIn("occupancy_columns = st.columns(4)", source)

    def test_recent_reports_use_narrow_operational_view(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        history_start = source.index("with history_tab:")
        history_source = source[history_start:]
        routine_source = history_source.split("with st.expander(", 1)[0]

        self.assertIn('"Services": (', routine_source)
        self.assertIn('"Food · Water · Power"', routine_source)
        self.assertNotIn('"Report",', routine_source)
        self.assertNotIn('"Barangay",', routine_source)

    def test_full_recent_report_fields_preserve_details(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('"Full recent report fields"', source)
        self.assertIn('"Barangay": update["barangay_name"]', source)
        self.assertIn('"Source": update["source"]', source)

    def test_registry_missing_address_uses_em_dash(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('"Address": center["address"] or "—"', source)
        self.assertIn('"Safe capacity *"', source)

    def test_cross_allocation_routine_view_preserves_full_source(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('"Full allocation source fields"', source)
        self.assertIn('"Recorded By": row["recorded_by"]', source)
        self.assertIn('"Recorded At": row["recorded_at"]', source)


if __name__ == "__main__":
    unittest.main()
