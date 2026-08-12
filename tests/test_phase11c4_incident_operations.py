from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "incidents.py"


class IncidentOperationsWorkspaceContracts(unittest.TestCase):
    def test_operational_header_and_event_strip(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn(
            'title="Incident & Response Operations"',
            source,
        )
        self.assertIn("render_operational_event_strip(", source)
        self.assertNotIn(
            'st.title("Incident & Response Operations")',
            source,
        )

    def test_command_picture_is_priority_and_resource_aware(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('title="Incident Command Picture"', source)
        self.assertIn('"Critical Incidents"', source)
        self.assertIn('"High-Priority Incidents"', source)
        self.assertIn('"Resources Available"', source)
        self.assertIn('"Resources Assigned"', source)
        self.assertIn('"No resources registered"', source)
        self.assertIn('"Response Resource Registry"', source)
        self.assertIn('"Not Set Up"', source)

    def test_open_incident_queue_is_priority_first(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn(
            "operational_incidents = sorted(",
            source,
        )
        self.assertIn('"Incident / Location"', source)
        self.assertIn('"People"', source)
        self.assertIn('"Age": format_age(', source)
        self.assertIn('"Closed incidents (', source)

    def test_selected_incident_has_operational_context(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('title="Response Coordination"', source)
        self.assertIn('title="Incident Lifecycle"', source)
        self.assertIn('"Report Age"', source)
        self.assertIn('"**Information source:**"', source)

    def test_new_incident_is_guided_but_semantics_remain(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for step in (
            'title="Location & Classification"',
            'title="Impact & Source"',
            'title="Review & Submit"',
        ):
            self.assertIn(step, source)

        for token in (
            "create_incident(",
            "submission_key=",
            "reporter_user_id=current_user.id",
            'type="primary"',
            '"New incidents start as Reported.',
        ):
            self.assertIn(token, source)

        step_two_position = source.index(
            'title="Impact & Source"'
        )
        persons_position = source.index(
            '"Persons affected"'
        )
        step_three_position = source.index(
            'title="Review & Submit"'
        )
        self.assertLess(step_two_position, persons_position)
        self.assertLess(persons_position, step_three_position)

    def test_resource_workflow_semantics_remain(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            "assign_resource_to_incident(",
            "release_resource_assignment(",
            "create_response_resource(",
            "set_resource_status(",
            "actor_user_id=current_user.id",
        ):
            self.assertIn(token, source)

    def test_incident_lifecycle_semantics_remain(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            "allowed_incident_transitions(",
            "change_incident_status(",
            "change_incident_priority(",
            "reopen_incident(",
            "current_user.role == ROLE_ADMINISTRATOR",
            '"Resolved", "Cancelled"',
        ):
            self.assertIn(token, source)

        self.assertIn(
            "disabled=not priority_change_pending",
            source,
        )

    def test_history_remains_auditable_and_compact(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        self.assertIn("get_incident_history(", source)
        self.assertIn('title="Incident Audit History"', source)
        self.assertIn('"Changed By"', source)
        self.assertIn('"Notes"', source)
        self.assertIn("width=420", source)

    def test_resource_empty_states_distinguish_registry_from_readiness(self):
        source = PAGE.read_text(encoding="utf-8-sig")
        for token in (
            "registered_resource_count = len(resources)",
            '"No response resources are registered or assigned. Add a "',
            'f"{len(active_resources)} active response "',
            '"Registry not set up"',
            '"Response resources are registered, but none are active.',
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
