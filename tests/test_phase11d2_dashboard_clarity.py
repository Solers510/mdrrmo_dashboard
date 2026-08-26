import ast
from pathlib import Path
import unittest

from utils.dashboard_view import (
    DashboardViewContractError,
    build_attention_follow_up_rows,
    select_dashboard_mode_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_PATH = PROJECT_ROOT / "utils" / "ui.py"
CSS_PATH = PROJECT_ROOT / "styles" / "mdrrmo.css"
DASHBOARD_PATH = PROJECT_ROOT / "pages" / "dashboard.py"
BARANGAY_PATH = PROJECT_ROOT / "pages" / "barangay_updates.py"
SERVICE_PATH = PROJECT_ROOT / "services" / "dashboard_service.py"


class DashboardClarityContracts(unittest.TestCase):
    def test_two_evacuation_locations_are_named(self):
        source = UI_PATH.read_text(encoding="utf-8-sig")

        for text in (
            "Inside Evacuation Centers",
            "Outside Evacuation Centers",
        ):
            self.assertIn(text, source)

        self.assertNotIn(
            "Affected — Not Recorded as Displaced",
            source,
        )

    def test_current_evacuation_picture_is_compact(self):
        source = UI_PATH.read_text(encoding="utf-8-sig")

        self.assertIn("Total Reported Affected Population", source)
        self.assertIn("Affected Barangays", source)
        self.assertIn("Operational Centers", source)
        self.assertIn("Inside Evacuation Centers", source)
        self.assertIn("Outside Evacuation Centers", source)
        self.assertIn("Currently Evacuated", source)
        self.assertIn(
            "Includes evacuees and affected residents who have not",
            source,
        )

    def test_location_panels_use_matching_operational_measures(self):
        source = UI_PATH.read_text(encoding="utf-8-sig")

        self.assertIn("Affected Families", source)
        self.assertIn("Affected Individuals", source)
        self.assertIn("Families", source)
        self.assertIn("Individuals", source)

    def test_displacement_layout_is_responsive(self):
        source = CSS_PATH.read_text(encoding="utf-8-sig")

        self.assertIn(".mdrrmo-evacuation-picture__locations", source)
        self.assertIn(
            ".mdrrmo-evacuation-picture__overall",
            source,
        )
        self.assertIn(".mdrrmo-evacuation-picture__metrics", source)
        self.assertIn("@media (max-width: 1050px)", source)
        self.assertIn("@media (max-width: 700px)", source)

    def test_dashboard_uses_plain_evacuation_overview_title(self):
        source = DASHBOARD_PATH.read_text(encoding="utf-8-sig")

        self.assertIn('title="Current Evacuation Summary"', source)

    @unittest.skip('UI Refactored')
    def test_partial_streamlit_reload_refreshes_new_ui_renderer(self):
        source = DASHBOARD_PATH.read_text(encoding="utf-8-sig")

        self.assertIn("import utils.ui as dashboard_ui", source)
        self.assertIn(
            'if not hasattr(\n    dashboard_ui,\n    "render_current_evacuation_picture",',
            source,
        )
        self.assertIn("dashboard_ui = importlib.reload(dashboard_ui)", source)
        self.assertNotIn(
            "    render_current_evacuation_picture,",
            source,
        )

    def test_main_summary_uses_full_evacuation_center_label(self):
        source = UI_PATH.read_text(encoding="utf-8-sig")

        self.assertIn(
            'label="Operational Centers"',
            source,
        )

    def test_summary_identifies_each_metric_source(self):
        source = UI_PATH.read_text(encoding="utf-8-sig")

        self.assertIn("Population figures: current barangay reports", source)
        self.assertIn(
            "Operational-center count: current evacuation-center reports",
            source,
        )
        self.assertIn("Barangay reports as of", source)
        self.assertIn("Center reports as of", source)

    def test_evacuation_tab_distinguishes_center_reported_totals(self):
        source = DASHBOARD_PATH.read_text(encoding="utf-8-sig")

        self.assertIn("Center-Reported Families", source)
        self.assertIn("Center-Reported Individuals", source)
        self.assertIn(
            "different inside-center totals",
            source,
        )
        self.assertIn(
            "Review Report Checks before publishing official figures.",
            source,
        )
        self.assertNotIn('"label": "Registered Families"', source)
        self.assertNotIn('"label": "Registered Individuals"', source)

    def test_report_checks_use_plain_source_labels(self):
        source = DASHBOARD_PATH.read_text(encoding="utf-8-sig")

        for text in (
            "Report Checks ",
            "Report Consistency Checks",
            "Matching Barangays",
            "Different Totals",
            "Missing Report",
            "Assignment Conflicts",
            "Families: Barangay / Center",
            "Individuals: Barangay / Center",
            "Center Report Age",
        ):
            self.assertIn(text, source)

        self.assertNotIn("Families B / EC", source)
        self.assertNotIn("Individuals B / EC", source)

    def test_barangay_population_check_avoids_not_displaced_label(self):
        source = BARANGAY_PATH.read_text(encoding="utf-8-sig")

        self.assertIn("Population Consistency Check", source)
        self.assertNotIn("Not Displaced", source)

    @unittest.skip('UI Refactored')
    def test_partial_streamlit_reload_cannot_crash_reconciliation(self):
        source = DASHBOARD_PATH.read_text(encoding="utf-8-sig")

        self.assertIn("_mode_specific_reconciliation_available", source)
        self.assertRegex(
            source,
            r'dashboard\.get\(\s*"reconciliation_summary"',
        )
        self.assertNotIn("Stop and restart Streamlit", source)
        self.assertNotIn(
            "The dashboard data service was updated while Streamlit was",
            source,
        )
        self.assertNotIn(
            'dashboard[\n        "provisional_reconciliation_summary"',
            source,
        )
        self.assertNotIn(
            'dashboard[\n        "official_reconciliation_summary"',
            source,
        )

        parsed = ast.parse(source)
        selected_nodes = [
            node
            for node in parsed.body
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name)
                    and target.id == "EMPTY_RECONCILIATION_SUMMARY"
                    for target in node.targets
                )
            )
            or (
                isinstance(node, ast.FunctionDef)
                and node.name == "select_reconciliation_payload"
            )
        ]
        namespace: dict[str, object] = {}
        exec(
            compile(
                ast.Module(body=selected_nodes, type_ignores=[]),
                str(DASHBOARD_PATH),
                "exec",
            ),
            namespace,
        )
        selector = namespace["select_reconciliation_payload"]
        legacy_bundle = {
            "reconciliation_summary": {"match": 7},
            "reconciliation_rows": [{"reconciliation_status": "Match"}],
            "reconciliation_available": True,
        }

        provisional = selector(
            legacy_bundle,
            view_mode="Provisional Operational",
        )
        official = selector(
            legacy_bundle,
            view_mode="Official Validated",
        )

        self.assertEqual(provisional[0]["match"], 7)
        self.assertTrue(provisional[2])
        self.assertFalse(provisional[3])
        self.assertEqual(official[0]["match"], 0)
        self.assertEqual(official[1], [])
        self.assertFalse(official[2])
        self.assertFalse(official[3])

    def test_dashboard_service_contract_is_versioned_and_reloaded(self):
        page_source = DASHBOARD_PATH.read_text(encoding="utf-8-sig")
        service_source = SERVICE_PATH.read_text(encoding="utf-8-sig")

        self.assertIn("DASHBOARD_BUNDLE_SCHEMA_VERSION = 2", service_source)
        self.assertIn(
            '"schema_version": DASHBOARD_BUNDLE_SCHEMA_VERSION',
            service_source,
        )
        self.assertIn(
            'import services.dashboard_service as dashboard_service',
            page_source,
        )
        self.assertIn(
            "dashboard_service = importlib.reload(",
            page_source,
        )
        self.assertIn(
            "select_dashboard_mode_payload(",
            page_source,
        )

    def test_mode_selector_never_combines_provisional_and_official_data(self):
        provisional_summary = {
            "affected_barangays": 4,
            "affected_families": 36,
            "affected_individuals": 140,
        }
        official_summary = {
            "affected_barangays": 3,
            "affected_families": 26,
            "affected_individuals": 100,
        }
        bundle = {
            "schema_version": 2,
            "provisional_summary": provisional_summary,
            "provisional_rows": [{"mode": "provisional"}],
            "provisional_evacuation_summary": {"open_centers": 2},
            "provisional_evacuation_rows": [{"mode": "provisional"}],
            "official_summary": official_summary,
            "official_rows": [{"mode": "official"}],
            "official_evacuation_summary": {"open_centers": 1},
            "official_evacuation_rows": [{"mode": "official"}],
        }

        provisional = select_dashboard_mode_payload(
            bundle,
            view_mode="Provisional Operational",
        )
        official = select_dashboard_mode_payload(
            bundle,
            view_mode="Official Validated",
        )

        self.assertIs(provisional["summary"], provisional_summary)
        self.assertEqual(provisional["rows"][0]["mode"], "provisional")
        self.assertEqual(
            provisional["evacuation_rows"][0]["mode"],
            "provisional",
        )
        self.assertIs(official["summary"], official_summary)
        self.assertEqual(official["rows"][0]["mode"], "official")
        self.assertEqual(
            official["evacuation_rows"][0]["mode"],
            "official",
        )

        with self.assertRaises(DashboardViewContractError):
            select_dashboard_mode_payload(
                {**bundle, "schema_version": 1},
                view_mode="Provisional Operational",
            )

    def test_attention_details_identify_the_source_record(self):
        details = build_attention_follow_up_rows(
            barangay_rows=[
                {
                    "barangay_name": "Munting Mapino",
                    "rescue_requests": 0,
                    "road_status": "Impassable",
                    "power_status": "Available",
                    "water_status": "Available",
                    "validation_status": "For Validation",
                    "affected_families": 10,
                    "affected_individuals": 40,
                    "inside_ec_families": 4,
                    "inside_ec_individuals": 16,
                    "outside_ec_families": 2,
                    "outside_ec_individuals": 8,
                }
            ],
            evacuation_rows=[
                {
                    "center_name": "Naic Elementary School",
                    "status": "Open",
                    "food_status": "Sufficient",
                    "water_status": "Sufficient",
                    "medical_cases": 1,
                }
            ],
            reconciliation_rows=[
                {
                    "barangay_name": "Munting Mapino",
                    "reconciliation_status": "Mismatch",
                }
            ],
        )

        self.assertIn(
            {
                "Area": "Barangay",
                "Location": "Munting Mapino",
                "What needs review": "Road reported as impassable",
            },
            details,
        )
        self.assertIn(
            {
                "Area": "Evacuation Center",
                "Location": "Naic Elementary School",
                "What needs review": "1 medical case recorded",
            },
            details,
        )
        self.assertIn(
            {
                "Area": "Report Check",
                "Location": "Munting Mapino",
                "What needs review": (
                    "Barangay and evacuation-center inside-EC totals differ"
                ),
            },
            details,
        )


if __name__ == "__main__":
    unittest.main()
