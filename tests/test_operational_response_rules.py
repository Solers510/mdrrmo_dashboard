import unittest

from services.cross_barangay_service import (
    CrossBarangayValidationError,
    validate_cross_allocation,
)
from services.incident_service import (
    allowed_incident_transitions,
)
from services.resource_service import (
    ResourceStateError,
    ResourceValidationError,
    validate_manual_resource_status,
)


class IncidentTransitionTests(unittest.TestCase):
    def test_reported_can_skip_forward_for_urgent_response(self):
        transitions = allowed_incident_transitions(
            "Reported"
        )
        self.assertIn(
            "Team Dispatched",
            transitions,
        )
        self.assertIn(
            "Resolved",
            transitions,
        )

    def test_responding_cannot_move_backward(self):
        transitions = allowed_incident_transitions(
            "Responding"
        )
        self.assertNotIn(
            "Verified",
            transitions,
        )
        self.assertIn(
            "Resolved",
            transitions,
        )

    def test_terminal_incident_has_no_normal_transition(self):
        self.assertEqual(
            allowed_incident_transitions("Resolved"),
            (),
        )
        self.assertEqual(
            allowed_incident_transitions("Cancelled"),
            (),
        )


class ResourceStateTests(unittest.TestCase):
    def test_assigned_status_is_not_manual(self):
        with self.assertRaises(ResourceValidationError):
            validate_manual_resource_status(
                current_status="Available",
                new_status="Assigned",
                has_active_assignment=False,
            )

    def test_active_assignment_blocks_readiness_change(self):
        with self.assertRaises(ResourceStateError):
            validate_manual_resource_status(
                current_status="Assigned",
                new_status="Maintenance",
                has_active_assignment=True,
            )

    def test_available_resource_can_enter_maintenance(self):
        validate_manual_resource_status(
            current_status="Available",
            new_status="Maintenance",
            has_active_assignment=False,
        )


class CrossBarangayAllocationTests(unittest.TestCase):
    def test_valid_foreign_allocation(self):
        validate_cross_allocation(
            families=5,
            individuals=20,
            other_families=3,
            other_individuals=10,
            center_families=20,
            center_individuals=80,
        )

    def test_combined_allocations_cannot_exceed_center(self):
        with self.assertRaises(
            CrossBarangayValidationError
        ):
            validate_cross_allocation(
                families=10,
                individuals=30,
                other_families=15,
                other_individuals=30,
                center_families=20,
                center_individuals=80,
            )

    def test_allocation_families_cannot_exceed_individuals(self):
        with self.assertRaises(
            CrossBarangayValidationError
        ):
            validate_cross_allocation(
                families=10,
                individuals=5,
                other_families=0,
                other_individuals=0,
                center_families=20,
                center_individuals=80,
            )


if __name__ == "__main__":
    unittest.main()
