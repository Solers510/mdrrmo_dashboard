import unittest

from services.data_integrity import (
    DataIntegrityValidationError,
    reconcile_population,
    validate_evacuation_occupancy,
    validate_flood_consistency,
)


class PopulationIntegrityTests(
    unittest.TestCase
):
    def test_valid_population_reconciliation(
        self,
    ):
        result = reconcile_population(
            affected_families=35,
            affected_individuals=140,
            inside_ec_families=23,
            inside_ec_individuals=93,
            outside_ec_families=8,
            outside_ec_individuals=31,
        )

        self.assertEqual(
            result.displaced_families,
            31,
        )

        self.assertEqual(
            result.displaced_individuals,
            124,
        )

        self.assertEqual(
            result.remaining_families,
            4,
        )

        self.assertEqual(
            result.remaining_individuals,
            16,
        )

    def test_displaced_families_cannot_exceed_affected(
        self,
    ):
        with self.assertRaises(
            DataIntegrityValidationError
        ):
            reconcile_population(
                affected_families=10,
                affected_individuals=50,
                inside_ec_families=20,
                inside_ec_individuals=30,
                outside_ec_families=10,
                outside_ec_individuals=15,
            )

    def test_remaining_families_cannot_exceed_remaining_people(
        self,
    ):
        with self.assertRaises(
            DataIntegrityValidationError
        ):
            reconcile_population(
                affected_families=66,
                affected_individuals=195,
                inside_ec_families=57,
                inside_ec_individuals=187,
                outside_ec_families=0,
                outside_ec_individuals=0,
            )

    def test_families_cannot_exceed_individuals(
        self,
    ):
        with self.assertRaises(
            DataIntegrityValidationError
        ):
            reconcile_population(
                affected_families=20,
                affected_individuals=10,
                inside_ec_families=0,
                inside_ec_individuals=0,
                outside_ec_families=0,
                outside_ec_individuals=0,
            )


class HazardIntegrityTests(
    unittest.TestCase
):
    def test_no_flooding_requires_zero_depth(
        self,
    ):
        with self.assertRaises(
            DataIntegrityValidationError
        ):
            validate_flood_consistency(
                flood_status="No Flooding",
                flood_depth_cm=10,
            )


class EvacuationIntegrityTests(
    unittest.TestCase
):
    def test_closed_center_requires_zero_occupants(
        self,
    ):
        with self.assertRaises(
            DataIntegrityValidationError
        ):
            validate_evacuation_occupancy(
                status="Closed",
                families=1,
                individuals=3,
                children=1,
                senior_citizens=0,
                pwd=0,
                pregnant_women=0,
                medical_cases=0,
                safe_capacity=100,
            )

    def test_over_capacity_requires_over_capacity_status(
        self,
    ):
        with self.assertRaises(
            DataIntegrityValidationError
        ):
            validate_evacuation_occupancy(
                status="Open",
                families=40,
                individuals=120,
                children=20,
                senior_citizens=10,
                pwd=3,
                pregnant_women=2,
                medical_cases=5,
                safe_capacity=100,
            )

    def test_vulnerable_categories_may_overlap(
        self,
    ):
        validate_evacuation_occupancy(
            status="Open",
            families=20,
            individuals=50,
            children=20,
            senior_citizens=20,
            pwd=20,
            pregnant_women=10,
            medical_cases=20,
            safe_capacity=100,
        )


if __name__ == "__main__":
    unittest.main()
