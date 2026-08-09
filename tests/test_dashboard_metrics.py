import unittest
from datetime import datetime, timezone

from services.dashboard_service import (
    _build_evacuation_summary,
    _build_reconciliation_summary,
    _build_summary,
)


NOW = datetime(
    2026,
    8,
    9,
    10,
    0,
    tzinfo=timezone.utc,
)


class DashboardSummaryTests(unittest.TestCase):
    def test_displacement_and_remaining_population(self):
        rows = [
            {
                "validation_status": "Submitted",
                "situation_status": "Affected",
                "affected_families": 10,
                "affected_individuals": 40,
                "inside_ec_families": 5,
                "inside_ec_individuals": 20,
                "outside_ec_families": 2,
                "outside_ec_individuals": 8,
                "rescue_requests": 1,
                "road_status": "Passable",
                "power_status": "Interrupted",
                "water_status": "Available",
                "recorded_at": NOW,
            }
        ]

        summary = _build_summary(
            rows=rows,
            total_barangays=30,
            usable_statuses={
                "Submitted",
                "For Validation",
                "Validated",
            },
        )

        self.assertEqual(
            summary["displaced_families"],
            7,
        )
        self.assertEqual(
            summary["displaced_individuals"],
            28,
        )
        self.assertEqual(
            summary[
                "affected_not_displaced_families"
            ],
            3,
        )
        self.assertEqual(
            summary[
                "affected_not_displaced_individuals"
            ],
            12,
        )
        self.assertEqual(
            summary[
                "population_consistency_issues"
            ],
            0,
        )
        self.assertEqual(
            summary["missing_reports"],
            29,
        )

    def test_pending_and_correction_counts(self):
        base = {
            "situation_status": "Monitoring",
            "affected_families": 0,
            "affected_individuals": 0,
            "inside_ec_families": 0,
            "inside_ec_individuals": 0,
            "outside_ec_families": 0,
            "outside_ec_individuals": 0,
            "rescue_requests": 0,
            "road_status": "Passable",
            "power_status": "Available",
            "water_status": "Available",
            "recorded_at": NOW,
        }

        rows = [
            {
                **base,
                "validation_status": "Submitted",
            },
            {
                **base,
                "validation_status": "For Validation",
            },
            {
                **base,
                "validation_status": "Needs Correction",
            },
            {
                **base,
                "validation_status": "Validated",
            },
        ]

        summary = _build_summary(
            rows=rows,
            total_barangays=30,
            usable_statuses={
                "Submitted",
                "For Validation",
                "Validated",
            },
        )

        self.assertEqual(
            summary["pending_validation"],
            2,
        )
        self.assertEqual(
            summary["needs_correction"],
            1,
        )
        self.assertEqual(
            summary["validated_reports"],
            1,
        )


class EvacuationDashboardTests(unittest.TestCase):
    def test_capacity_and_operational_counts(self):
        rows = [
            {
                "validation_status": "Submitted",
                "status": "Open",
                "families": 5,
                "individuals": 20,
                "safe_capacity": 50,
                "children": 4,
                "senior_citizens": 2,
                "pwd": 1,
                "pregnant_women": 1,
                "medical_cases": 1,
                "food_status": "Sufficient",
                "water_status": "Sufficient",
                "electricity_status": "Available",
                "recorded_at": NOW,
            },
            {
                "validation_status": "Validated",
                "status": "Over Capacity",
                "families": 15,
                "individuals": 60,
                "safe_capacity": 50,
                "children": 10,
                "senior_citizens": 5,
                "pwd": 2,
                "pregnant_women": 2,
                "medical_cases": 3,
                "food_status": "Critical",
                "water_status": "Critical",
                "electricity_status": "Unavailable",
                "recorded_at": NOW,
            },
        ]

        summary = _build_evacuation_summary(
            rows=rows,
            usable_statuses={
                "Submitted",
                "For Validation",
                "Validated",
            },
        )

        self.assertEqual(
            summary["open_centers"],
            2,
        )
        self.assertEqual(
            summary["over_capacity_centers"],
            1,
        )
        self.assertEqual(
            summary["individuals"],
            80,
        )
        self.assertEqual(
            summary["safe_capacity"],
            100,
        )
        self.assertAlmostEqual(
            summary[
                "capacity_utilization_percent"
            ],
            80.0,
        )


class ReconciliationSummaryTests(unittest.TestCase):
    def test_reconciliation_status_counts(self):
        rows = [
            {
                "reconciliation_status": "Match",
            },
            {
                "reconciliation_status": "Mismatch",
            },
            {
                "reconciliation_status": "No EC Report",
            },
            {
                "reconciliation_status": "No Barangay Report",
            },
            {
                "reconciliation_status": "Allocation Conflict",
            },
            {
                "reconciliation_status": "No Current Data",
            },
        ]

        summary = _build_reconciliation_summary(
            rows
        )

        self.assertEqual(
            summary["match"],
            1,
        )
        self.assertEqual(
            summary["mismatch"],
            1,
        )
        self.assertEqual(
            summary["missing_source"],
            2,
        )
        self.assertEqual(
            summary["allocation_conflict"],
            1,
        )
        self.assertEqual(
            summary["no_current_data"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
