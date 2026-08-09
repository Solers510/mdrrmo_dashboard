from uuid import uuid4

import pandas as pd
import streamlit as st

from config.access_control import (
    PERMISSION_MANAGE_INCIDENTS,
    ROLE_ADMINISTRATOR,
)
from services.barangay_service import (
    BarangayServiceError,
    list_active_barangays,
)
from services.event_service import (
    EventDataIntegrityError,
    get_active_event_summary,
)
from services.incident_service import (
    INCIDENT_PRIORITIES,
    INCIDENT_TYPES,
    DuplicateIncidentSubmissionError,
    IncidentAuthorizationError,
    IncidentDataIntegrityError,
    IncidentServiceError,
    IncidentStateError,
    IncidentValidationError,
    NoActiveEventError,
    allowed_incident_transitions,
    change_incident_priority,
    change_incident_status,
    create_incident,
    get_incident_history,
    list_recent_incidents,
    reopen_incident,
)
from services.resource_service import (
    MANUAL_RESOURCE_STATUSES,
    RESOURCE_TYPES,
    ResourceAuthorizationError,
    ResourceDataIntegrityError,
    ResourceServiceError,
    ResourceStateError,
    ResourceValidationError,
    assign_resource_to_incident,
    create_response_resource,
    list_incident_assignments,
    list_response_resources,
    release_resource_assignment,
    set_resource_status,
)
from utils.auth import require_permission


current_user = require_permission(
    PERMISSION_MANAGE_INCIDENTS
)


def show_error(error: Exception) -> None:
    if isinstance(error, (IncidentStateError, ResourceStateError)):
        st.warning(str(error))
    else:
        st.error(str(error))


st.title("Incident & Response Operations")
st.caption(
    "Record incidents, track operational status, dispatch response "
    "resources, and preserve a complete incident history."
)

success_message = st.session_state.pop(
    "incident_success",
    None,
)
if success_message:
    st.success(success_message)

try:
    active_event = get_active_event_summary()
except EventDataIntegrityError as error:
    st.error(str(error))
    st.stop()
except Exception:
    st.error(
        "The active disaster event could not be loaded."
    )
    st.stop()

if active_event is None:
    st.warning(
        "No active disaster event exists. "
        "Create or reopen an event before managing incidents."
    )
    st.stop()

event_columns = st.columns(3)
event_columns[0].metric(
    "Active Event",
    str(active_event["event_name"]),
)
event_columns[1].metric(
    "Alert Level",
    str(active_event["alert_code"]),
)
event_columns[2].metric(
    "EOC Status",
    str(active_event["eoc_status"]),
)

try:
    barangays = list_active_barangays()
    incidents = list_recent_incidents(limit=100)
    resources = list_response_resources()
except (
    BarangayServiceError,
    IncidentServiceError,
    ResourceServiceError,
) as error:
    st.error(str(error))
    st.stop()

barangay_label_to_id = {
    f"{record['name']} — {record['psgc_code']}": int(record["id"])
    for record in barangays
}

open_incidents = [
    incident
    for incident in incidents
    if incident["status"] not in {"Resolved", "Cancelled"}
]

summary_columns = st.columns(4)
summary_columns[0].metric(
    "Open Incidents",
    len(open_incidents),
)
summary_columns[1].metric(
    "Critical",
    sum(
        1
        for incident in open_incidents
        if incident["priority"] == "Critical"
    ),
)
summary_columns[2].metric(
    "Resources Available",
    sum(
        1
        for resource in resources
        if resource["status"] == "Available"
        and resource["is_active"]
    ),
)
summary_columns[3].metric(
    "Resources Assigned",
    sum(
        1
        for resource in resources
        if resource["status"] == "Assigned"
        and resource["is_active"]
    ),
)

incident_tab, new_tab, resource_tab, history_tab = st.tabs(
    (
        "Incident Operations",
        "New Incident",
        "Response Resources",
        "Incident History",
    )
)

with new_tab:
    st.subheader("Record New Incident")

    if not barangays:
        st.warning(
            "No active barangays are available."
        )
    else:
        nonce = int(
            st.session_state.setdefault(
                "incident_form_nonce",
                0,
            )
        )
        prefix = f"incident_{nonce}_"
        submission_key_name = (
            f"incident_submission_key_{nonce}"
        )
        if submission_key_name not in st.session_state:
            st.session_state[submission_key_name] = str(
                uuid4()
            )

        with st.form(
            f"incident_form_{nonce}",
            clear_on_submit=False,
        ):
            selected_barangay = st.selectbox(
                "Barangay *",
                options=list(barangay_label_to_id),
                key=prefix + "barangay",
            )

            exact_location = st.text_input(
                "Exact location or landmark *",
                key=prefix + "location",
            )

            row = st.columns(3)
            incident_type = row[0].selectbox(
                "Incident type *",
                options=INCIDENT_TYPES,
                key=prefix + "type",
            )
            priority = row[1].selectbox(
                "Priority *",
                options=INCIDENT_PRIORITIES,
                index=1,
                key=prefix + "priority",
            )
            persons_affected = row[2].number_input(
                "Persons affected",
                min_value=0,
                step=1,
                key=prefix + "persons",
            )

            description = st.text_area(
                "Incident description *",
                height=130,
                key=prefix + "description",
            )

            source = st.text_input(
                "Information source *",
                placeholder=(
                    "Caller, barangay official, field team, "
                    "radio message, official report"
                ),
                key=prefix + "source",
            )

            st.info(
                "New incidents start as Reported. "
                "Status changes are recorded separately so the "
                "operational timeline remains auditable."
            )

            confirmation = st.checkbox(
                "I reviewed the location, description, priority, "
                "persons affected, and source.",
                key=prefix + "confirmation",
            )

            submitted = st.form_submit_button(
                "Save Incident",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not confirmation:
                st.error(
                    "Confirm the incident information before saving."
                )
            else:
                try:
                    incident_id = create_incident(
                        barangay_id=barangay_label_to_id[
                            selected_barangay
                        ],
                        exact_location=exact_location,
                        incident_type=incident_type,
                        description=description,
                        priority=priority,
                        persons_affected=int(
                            persons_affected
                        ),
                        source=source,
                        submission_key=st.session_state[
                            submission_key_name
                        ],
                        reporter_user_id=current_user.id,
                    )
                except (
                    IncidentValidationError,
                    IncidentAuthorizationError,
                    IncidentDataIntegrityError,
                    DuplicateIncidentSubmissionError,
                    NoActiveEventError,
                    IncidentServiceError,
                ) as error:
                    show_error(error)
                except Exception:
                    st.error(
                        "The incident could not be saved. "
                        "Your entries were kept."
                    )
                else:
                    st.session_state[
                        "incident_form_nonce"
                    ] = nonce + 1
                    st.session_state.pop(
                        submission_key_name,
                        None,
                    )
                    st.session_state[
                        "incident_success"
                    ] = (
                        f"Incident #{incident_id} "
                        "was recorded successfully."
                    )
                    st.rerun()

with incident_tab:
    st.subheader("Active Incident Operations")

    if not incidents:
        st.info(
            "No incidents have been recorded for the active event."
        )
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Control": incident["control_number"],
                        "Barangay": incident["barangay_name"],
                        "Type": incident["incident_type"],
                        "Priority": incident["priority"],
                        "Status": incident["status"],
                        "Persons Affected": incident["persons_affected"],
                        "Location": incident["exact_location"],
                        "Reported At": incident["reported_at"],
                    }
                    for incident in incidents
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        incident_by_id = {
            int(incident["id"]): incident
            for incident in incidents
        }

        selected_id = st.selectbox(
            "Select incident",
            options=list(incident_by_id),
            format_func=lambda incident_id: (
                f"{incident_by_id[incident_id]['control_number']} — "
                f"{incident_by_id[incident_id]['barangay_name']} — "
                f"{incident_by_id[incident_id]['status']}"
            ),
            key="incident_operations_select",
        )

        selected = incident_by_id[selected_id]

        st.markdown(
            f"### {selected['control_number']}"
        )

        details = st.columns(4)
        details[0].metric(
            "Priority",
            str(selected["priority"]),
        )
        details[1].metric(
            "Status",
            str(selected["status"]),
        )
        details[2].metric(
            "Persons Affected",
            int(selected["persons_affected"]),
        )
        details[3].metric(
            "Barangay",
            str(selected["barangay_name"]),
        )

        st.write(
            "**Location:**",
            selected["exact_location"],
        )
        st.write(
            "**Type:**",
            selected["incident_type"],
        )
        st.write(
            "**Description:**",
            selected["description"],
        )
        st.write(
            "**Source:**",
            selected["source"],
        )
        st.write(
            "**Latest action/notes:**",
            selected["action_taken"]
            or "No action notes yet.",
        )

        assignments = list_incident_assignments(
            incident_id=selected_id
        )

        st.markdown("#### Assigned Response Resources")

        if not assignments:
            st.info(
                "No active response resources are assigned."
            )
        else:
            st.dataframe(
                pd.DataFrame(assignments),
                use_container_width=True,
                hide_index=True,
            )

        available_resources = [
            resource
            for resource in resources
            if (
                resource["is_active"]
                and resource["status"] == "Available"
            )
        ]

        if selected["status"] not in {"Resolved", "Cancelled"}:
            assign_columns = st.columns(2)

            with assign_columns[0]:
                if available_resources:
                    resource_by_id = {
                        int(resource["id"]): resource
                        for resource in available_resources
                    }
                    selected_resource_id = st.selectbox(
                        "Available resource",
                        options=list(resource_by_id),
                        format_func=lambda resource_id: (
                            f"{resource_by_id[resource_id]['resource_code']} — "
                            f"{resource_by_id[resource_id]['name']} "
                            f"({resource_by_id[resource_id]['resource_type']})"
                        ),
                        key=f"assign_resource_{selected_id}",
                    )

                    assignment_notes = st.text_input(
                        "Dispatch/assignment notes",
                        key=f"assignment_notes_{selected_id}",
                    )

                    if st.button(
                        "Assign Resource",
                        key=f"assign_resource_button_{selected_id}",
                    ):
                        try:
                            assignment_id = (
                                assign_resource_to_incident(
                                    incident_id=selected_id,
                                    resource_id=int(
                                        selected_resource_id
                                    ),
                                    notes=assignment_notes,
                                    actor_user_id=current_user.id,
                                )
                            )
                        except ResourceServiceError as error:
                            show_error(error)
                        else:
                            st.session_state[
                                "incident_success"
                            ] = (
                                f"Response resource assignment "
                                f"#{assignment_id} saved."
                            )
                            st.rerun()
                else:
                    st.info(
                        "No resources are currently Available."
                    )

            with assign_columns[1]:
                if assignments:
                    assignment_by_id = {
                        int(row["assignment_id"]): row
                        for row in assignments
                    }
                    release_id = st.selectbox(
                        "Active assignment to release",
                        options=list(assignment_by_id),
                        format_func=lambda assignment_id: (
                            f"{assignment_by_id[assignment_id]['resource_code']} — "
                            f"{assignment_by_id[assignment_id]['resource_name']}"
                        ),
                        key=f"release_assignment_{selected_id}",
                    )

                    release_notes = st.text_input(
                        "Release notes *",
                        key=f"release_notes_{selected_id}",
                    )

                    if st.button(
                        "Release Resource",
                        key=f"release_resource_button_{selected_id}",
                    ):
                        try:
                            release_resource_assignment(
                                assignment_id=int(
                                    release_id
                                ),
                                notes=release_notes,
                                actor_user_id=current_user.id,
                            )
                        except ResourceServiceError as error:
                            show_error(error)
                        else:
                            st.session_state[
                                "incident_success"
                            ] = (
                                "Response resource released."
                            )
                            st.rerun()

        st.divider()

        transition_columns = st.columns(2)

        with transition_columns[0]:
            st.markdown("#### Change Incident Status")

            allowed = allowed_incident_transitions(
                str(selected["status"])
            )

            if allowed:
                new_status = st.selectbox(
                    "New status",
                    options=allowed,
                    key=f"status_{selected_id}",
                )
                status_notes = st.text_area(
                    "Reason / action taken *",
                    height=100,
                    key=f"status_notes_{selected_id}",
                )

                if (
                    new_status in {
                        "Team Dispatched",
                        "Responding",
                    }
                    and not assignments
                ):
                    st.warning(
                        "No registered response resource is currently "
                        "assigned. You may continue if the response uses "
                        "an external or unregistered resource."
                    )

                if st.button(
                    "Apply Status Change",
                    type="primary",
                    key=f"status_button_{selected_id}",
                ):
                    try:
                        change_incident_status(
                            incident_id=selected_id,
                            new_status=new_status,
                            notes=status_notes,
                            actor_user_id=current_user.id,
                        )
                    except IncidentServiceError as error:
                        show_error(error)
                    else:
                        st.session_state[
                            "incident_success"
                        ] = (
                            f"{selected['control_number']} "
                            f"was marked {new_status}."
                        )
                        st.rerun()
            else:
                st.info(
                    "This incident is closed. "
                    "Only an Administrator may reopen it."
                )

        with transition_columns[1]:
            st.markdown("#### Change Priority")

            priority_index = (
                INCIDENT_PRIORITIES.index(
                    str(selected["priority"])
                )
            )
            new_priority = st.selectbox(
                "New priority",
                options=INCIDENT_PRIORITIES,
                index=priority_index,
                key=f"priority_{selected_id}",
            )
            priority_reason = st.text_area(
                "Reason for priority change",
                height=100,
                key=f"priority_reason_{selected_id}",
            )

            if st.button(
                "Apply Priority Change",
                key=f"priority_button_{selected_id}",
            ):
                try:
                    change_incident_priority(
                        incident_id=selected_id,
                        new_priority=new_priority,
                        reason=priority_reason,
                        actor_user_id=current_user.id,
                    )
                except IncidentServiceError as error:
                    show_error(error)
                else:
                    st.session_state[
                        "incident_success"
                    ] = (
                        f"{selected['control_number']} "
                        f"priority changed to {new_priority}."
                    )
                    st.rerun()

        if (
            current_user.role == ROLE_ADMINISTRATOR
            and selected["status"] in {"Resolved", "Cancelled"}
        ):
            st.divider()
            st.markdown("#### Administrator Reopen")

            reopen_reason = st.text_area(
                "Reason for reopening *",
                key=f"reopen_reason_{selected_id}",
            )
            reopen_confirm = st.checkbox(
                "I confirm this closed incident must return to "
                "active operational handling.",
                key=f"reopen_confirm_{selected_id}",
            )

            if st.button(
                "Reopen Incident",
                disabled=not reopen_confirm,
                key=f"reopen_button_{selected_id}",
            ):
                try:
                    reopen_incident(
                        incident_id=selected_id,
                        reason=reopen_reason,
                        actor_user_id=current_user.id,
                    )
                except IncidentServiceError as error:
                    show_error(error)
                else:
                    st.session_state[
                        "incident_success"
                    ] = (
                        f"{selected['control_number']} reopened."
                    )
                    st.rerun()

with resource_tab:
    st.subheader("Response Resource Readiness")

    create_tab, readiness_tab = st.tabs(
        (
            "Add Resource",
            "Readiness Status",
        )
    )

    with create_tab:
        with st.form(
            "create_response_resource_form",
            clear_on_submit=False,
        ):
            resource_code = st.text_input(
                "Resource code *",
                placeholder="TEAM-ALPHA, AMB-01, BOAT-01",
            )
            resource_name = st.text_input(
                "Resource name *"
            )
            resource_type = st.selectbox(
                "Resource type *",
                options=RESOURCE_TYPES,
            )
            subtype = st.text_input(
                "Subtype / class",
                placeholder=(
                    "Ambulance, rescue boat, SAR team, generator"
                ),
            )
            resource_details = st.text_area(
                "Details",
                placeholder=(
                    "Capacity, call sign, equipment, home base, "
                    "or other operational notes."
                ),
            )
            resource_confirm = st.checkbox(
                "I verified this response resource record."
            )
            resource_submitted = st.form_submit_button(
                "Add Response Resource",
                type="primary",
                use_container_width=True,
            )

        if resource_submitted:
            if not resource_confirm:
                st.error(
                    "Confirm the resource record before saving."
                )
            else:
                try:
                    resource_id = create_response_resource(
                        resource_code=resource_code,
                        name=resource_name,
                        resource_type=resource_type,
                        subtype=subtype,
                        details=resource_details,
                        actor_user_id=current_user.id,
                    )
                except ResourceServiceError as error:
                    show_error(error)
                else:
                    st.session_state[
                        "incident_success"
                    ] = (
                        f"Response resource #{resource_id} added."
                    )
                    st.rerun()

    with readiness_tab:
        if not resources:
            st.info(
                "No response resources have been registered."
            )
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Code": resource["resource_code"],
                            "Name": resource["name"],
                            "Type": resource["resource_type"],
                            "Subtype": resource["subtype"],
                            "Status": resource["status"],
                            "Details": resource["details"],
                        }
                        for resource in resources
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

            resource_by_id = {
                int(resource["id"]): resource
                for resource in resources
                if resource["is_active"]
            }

            selected_resource = st.selectbox(
                "Select resource",
                options=list(resource_by_id),
                format_func=lambda resource_id: (
                    f"{resource_by_id[resource_id]['resource_code']} — "
                    f"{resource_by_id[resource_id]['name']} "
                    f"({resource_by_id[resource_id]['status']})"
                ),
                key="readiness_resource_select",
            )

            selected_resource_row = resource_by_id[
                selected_resource
            ]

            if selected_resource_row["status"] == "Assigned":
                st.warning(
                    "Assigned resources must be released from their "
                    "incident before readiness status can change."
                )
            else:
                current_index = (
                    MANUAL_RESOURCE_STATUSES.index(
                        str(selected_resource_row["status"])
                    )
                    if selected_resource_row["status"]
                    in MANUAL_RESOURCE_STATUSES
                    else 0
                )
                readiness_status = st.selectbox(
                    "Readiness status",
                    options=MANUAL_RESOURCE_STATUSES,
                    index=current_index,
                    key="readiness_status_select",
                )

                if st.button(
                    "Update Readiness",
                    key="readiness_update_button",
                ):
                    try:
                        set_resource_status(
                            resource_id=int(
                                selected_resource
                            ),
                            new_status=readiness_status,
                            actor_user_id=current_user.id,
                        )
                    except ResourceServiceError as error:
                        show_error(error)
                    else:
                        st.session_state[
                            "incident_success"
                        ] = (
                            "Resource readiness status updated."
                        )
                        st.rerun()

with history_tab:
    st.subheader("Incident Audit History")

    if not incidents:
        st.info(
            "No incident history is available."
        )
    else:
        history_incident_by_id = {
            int(incident["id"]): incident
            for incident in incidents
        }

        history_selected_id = st.selectbox(
            "Incident",
            options=list(history_incident_by_id),
            format_func=lambda incident_id: (
                f"{history_incident_by_id[incident_id]['control_number']} — "
                f"{history_incident_by_id[incident_id]['barangay_name']}"
            ),
            key="incident_history_select",
        )

        try:
            history_rows = get_incident_history(
                incident_id=int(
                    history_selected_id
                ),
                limit=100,
            )
        except IncidentServiceError as error:
            st.error(str(error))
            history_rows = []

        if not history_rows:
            st.info(
                "No history entries exist for this incident."
            )
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "When": row["effective_at"],
                            "Change": row["change_type"],
                            "Field": row["field_name"],
                            "Previous": row["previous_value"],
                            "New": row["new_value"],
                            "Notes": row["notes"],
                            "Changed By": row["changed_by"],
                        }
                        for row in history_rows
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
