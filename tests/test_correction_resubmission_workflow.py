from pathlib import Path
from types import SimpleNamespace
import unittest

from services.barangay_service import (
    _barangay_correction_snapshot,
)
from services.evacuation_service import (
    _evacuation_correction_snapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CorrectionSnapshotTests(unittest.TestCase):
    def test_barangay_correction_snapshot_preserves_review_and_form_data(self):
        report = SimpleNamespace(
            id=11,
            event_id=1,
            barangay_id=2,
            validation_status="Needs Correction",
            situation_status="Monitoring",
            affected_families=10,
            affected_individuals=40,
            inside_ec_families=2,
            inside_ec_individuals=8,
            outside_ec_families=1,
            outside_ec_individuals=4,
            flood_status="No Flooding",
            flood_depth_cm=0,
            road_status="Passable",
            power_status="Normal",
            water_status="Normal",
            rescue_requests=0,
            source="UAT source",
            remarks="Original remarks",
            reviewed_by="Validator — Validator",
            review_notes="Verify family count.",
            reviewed_at=None,
            recorded_at=None,
        )

        result = _barangay_correction_snapshot(report)

        self.assertEqual(result["id"], 11)
        self.assertEqual(result["affected_individuals"], 40)
        self.assertEqual(result["review_notes"], "Verify family count.")
        self.assertEqual(result["validation_status"], "Needs Correction")

    def test_evacuation_correction_snapshot_preserves_review_and_form_data(self):
        report = SimpleNamespace(
            id=7,
            event_id=1,
            evacuation_center_id=2,
            validation_status="Needs Correction",
            status="Open",
            families=5,
            individuals=20,
            children=4,
            senior_citizens=3,
            pwd=2,
            pregnant_women=1,
            medical_cases=1,
            food_status="Sufficient",
            water_status="Critical",
            electricity_status="Available",
            sanitation_status="Limited",
            source="UAT source",
            remarks="Original remarks",
            reviewed_by="Validator — Validator",
            review_notes="Verify occupancy.",
            reviewed_at=None,
            recorded_at=None,
        )

        result = _evacuation_correction_snapshot(report)

        self.assertEqual(result["id"], 7)
        self.assertEqual(result["individuals"], 20)
        self.assertEqual(result["water_status"], "Critical")
        self.assertEqual(result["review_notes"], "Verify occupancy.")


class CorrectionPageContractTests(unittest.TestCase):
    def test_barangay_page_surfaces_pending_correction(self):
        source = (
            PROJECT_ROOT / "pages" / "barangay_updates.py"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("get_pending_barangay_correction", source)
        self.assertIn("Correction Required — Barangay Report", source)
        self.assertIn("Validator instructions", source)
        self.assertIn("Submitting the corrected report will supersede", source)

    def test_evacuation_page_surfaces_pending_correction(self):
        source = (
            PROJECT_ROOT / "pages" / "evacuation_centers.py"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("get_pending_evacuation_correction", source)
        self.assertIn("Correction Required — Evacuation-Center", source)
        self.assertIn("Validator instructions", source)
        self.assertIn("will supersede Report", source)


if __name__ == "__main__":
    unittest.main()
