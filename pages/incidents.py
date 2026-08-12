from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

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
from utils.ui import (
    render_attention_required,
    render_dashboard_section_header,
    render_kpi_grid,
    render_operational_event_strip,
    render_operational_page_header,
    render_workflow_section,
)


current_user = require_permission(
    PERMISSION_MANAGE_INCIDENTS
)


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

INCIDENT_PRIORITY_RANK = {
    "Low": 0,
    "Moderate": 1,
    "High": 2,
    "Critical": 3,
}


def display_event_name(event: dict[str, object]) -> str:
    classification = event.get("classification")
    name = str(event["event_name"])

    if classification is not None and str(classification).strip():
        return f"{classification} {name}"

    return name


def display_sitrep(event: dict[str, object]) -> str:
    value = event.get("current_sitrep_number")
    return "Not set" if value in {None, ""} else str(value)


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "Not available"

    return value.astimezone(MANILA_TIMEZONE).strftime(
        "%d %B %Y, %I:%M %p"
    )


def format_age(value: datetime | None) -> str:
    if value is None:
        return "—"

    localized = value.astimezone(MANILA_TIMEZONE)
    now = datetime.now(MANILA_TIMEZONE)
    seconds = max(int((now - localized).total_seconds()), 0)

    if seconds < 60:
        return "<1m"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"

    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"

    return f"{hours // 24}d"


def incident_sort_key(incident: dict[str, object]) -> tuple[int, float]:
    priority_rank = INCIDENT_PRIORITY_RANK.get(
        str(incident["priority"]),
        -1,
    )
    reported_at = incident.get("reported_at")
    timestamp = (
        reported_at.timestamp()
        if isinstance(reported_at, datetime)
        else 0.0
    )
    return priority_rank, timestamp


def show_error(error: Exception) -> None:
    if isinstance(error, (IncidentStateError, ResourceStateError)):
        st.warning(str(error))
    else:
        st.error(str(error))


render_operational_page_header(
    title="Incident & Response Operations",
    subtitle=(
        "Record and prioritize incidents, coordinate response resources, "
        "manage incident lifecycle, and preserve an auditable operational history."
    ),
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

render_operational_event_strip(
    event_name=display_event_name(active_event),
    hazard_type=str(active_event["hazard_type"]),
    alert_code=str(active_event["alert_code"]),
    eoc_status=str(active_event["eoc_status"]),
    sitrep=display_sitrep(active_event),
    official_reference=(
        str(active_event["official_reference"])
        if active_event.get("official_reference")
        else None
    ),
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
closed_incidents = [
    incident
    for incident in incidents
    if incident["status"] in {"Resolved", "Cancelled"}
]
operational_incidents = sorted(
    open_incidents,
    key=incident_sort_key,
    reverse=True,
)
registered_resource_count = len(resources)
active_resources = [
    resource
    for resource in resources
    if resource["is_active"]
]
available_resource_count = sum(
    1
    for resource in active_resources
    if resource["status"] == "Available"
)
assigned_resource_count = sum(
    1
    for resource in active_resources
    if resource["status"] == "Assigned"
)
critical_incident_count = sum(
    1
    for incident in open_incidents
    if incident["priority"] == "Critical"
)
high_incident_count = sum(
    1
    for incident in open_incidents
    if incident["priority"] == "High"
)

render_dashboard_section_header(
    title="Incident Command Picture",
    subtitle=(
        "Current incident workload and response-resource readiness for the "
        "active disaster event."
    ),
)

render_kpi_grid(
    [
        {
            "label": "Open Incidents",
            "value": len(open_incidents),
        },
        {
            "label": "Critical",
            "value": critical_incident_count,
        },
        {
            "label": "High Priority",
            "value": high_incident_count,
        },
        {
            "label": "Resources Available",
            "value": available_resource_count,
            "meta": (
                "No resources registered"
                if registered_resource_count == 0
                else f"{len(active_resources)} active registered"
            ),
        },
        {
            "label": "Resources Assigned",
            "value": assigned_resource_count,
        },
    ]
)

attention_items = []
if critical_incident_count:
    attention_items.append(
        {
            "label": "Critical Incidents",
            "value": critical_incident_count,
            "tone": "danger",
        }
    )
if high_incident_count:
    attention_items.append(
        {
            "label": "High-Priority Incidents",
            "value": high_incident_count,
            "tone": "warning",
        }
    )
if open_incidents:
    if registered_resource_count == 0:
        attention_items.append(
            {
                "label": "Response Resource Registry",
                "value": "Not Set Up",
                "tone": "warning",
            }
        )
    elif available_resource_count == 0:
        attention_items.append(
            {
                "label": "Available Resources",
                "value": 0,
                "tone": "danger",
            }
        )

if attention_items:
    render_attention_required(attention_items)

incident_tab, new_tab, resource_tab, history_tab = st.tabs(
    (
        f"Incident Operations ({len(open_incidents)})",
        "New Incident",
        f"Response Resources ({len(resources)})",
        "Incident History",
    )
)

with new_tab:
    render_dashboard_section_header(
        title="Record New Incident",
        subtitle=(
            "Capture the incident location, operational priority, affected "
            "population, description, and information source."
        ),
    )

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
            render_workflow_section(
                step=1,
                title="Location & Classification",
                subtitle=(
                    "Identify where the incident occurred and classify the "
                    "operational problem before entering impact details."
                ),
            )

            selected_barangay = st.selectbox(
                "Barangay *",
                options=list(barangay_label_to_id),
                key=prefix + "barangay",
            )

            exact_location = st.text_input(
                "Exact location or landmark *",
                key=prefix + "location",
            )

            classification_columns = st.columns(2)
            incident_type = classification_columns[0].selectbox(
                "Incident type *",
                options=INCIDENT_TYPES,
                key=prefix + "type",
            )
            priority = classification_columns[1].selectbox(
                "Priority *",
                options=INCIDENT_PRIORITIES,
                index=1,
                key=prefix + "priority",
            )

            render_workflow_section(
                step=2,
                title="Impact & Source",
                subtitle=(
                    "Describe the incident, estimate the people directly "
                    "affected, and identify the reporting source."
                ),
            )

            persons_affected = st.number_input(
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

            render_workflow_section(
                step=3,
                title="Review & Submit",
                subtitle=(
                    "Confirm the report before creating the incident. New "
                    "incidents begin as Reported and later status changes remain auditable."
                ),
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
                width="stretch",
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
    render_dashboard_section_header(
        title="Active Incident Operations",
        subtitle=(
            "Open incidents are ordered by operational priority and recency. "
            "Select an incident to coordinate resources or change lifecycle state."
        ),
    )

    if not incidents:
        st.info(
            "No incidents have been recorded for the active event."
        )
    else:
        if not operational_incidents:
            st.success(
                "No active incident currently requires operational handling."
            )
        else:
            incident_queue_rows = [
                {
                    "Control": incident["control_number"],
                    "Priority": incident["priority"],
                    "Status": incident["status"],
                    "Barangay": incident["barangay_name"],
                    "Incident / Location": (
                        f"{incident['incident_type']} · "
                        f"{incident['exact_location']}"
                    ),
                    "People": int(incident["persons_affected"]),
                    "Age": format_age(incident["reported_at"]),
                }
                for incident in operational_incidents
            ]

            st.dataframe(
                pd.DataFrame(incident_queue_rows),
                width="stretch",
                hide_index=True,
                column_config={
                    "Control": st.column_config.TextColumn(
                        "Control",
                        width=120,
                        pinned=True,
                    ),
                    "Priority": st.column_config.TextColumn(
                        "Priority",
                        width=80,
                    ),
                    "Status": st.column_config.TextColumn(
                        "Status",
                        width=105,
                    ),
                    "Barangay": st.column_config.TextColumn(
                        "Barangay",
                        width=145,
                    ),
                    "Incident / Location": st.column_config.TextColumn(
                        "Incident / Location",
                        width=260,
                    ),
                    "People": st.column_config.NumberColumn(
                        "People",
                        width=65,
                        format="%d",
                    ),
                    "Age": st.column_config.TextColumn(
                        "Age",
                        width=55,
                    ),
                },
            )

        if closed_incidents:
            with st.expander(
                f"Closed incidents ({len(closed_incidents)})",
                expanded=False,
            ):
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Control": incident["control_number"],
                                "Priority": incident["priority"],
                                "Status": incident["status"],
                                "Barangay": incident["barangay_name"],
                                "Type": incident["incident_type"],
                                "Reported": format_datetime(
                                    incident["reported_at"]
                                ),
                            }
                            for incident in closed_incidents
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )

        incident_by_id = {
            int(incident["id"]): incident
            for incident in incidents
        }

        incident_selection_ids = [
            int(incident["id"])
            for incident in operational_incidents
        ] + [
            int(incident["id"])
            for incident in closed_incidents
        ]

        selected_id = st.selectbox(
            "Select incident for operations or review",
            options=incident_selection_ids,
            format_func=lambda incident_id: (
                f"{incident_by_id[incident_id]['control_number']} — "
                f"{incident_by_id[incident_id]['priority']} — "
                f"{incident_by_id[incident_id]['status']} — "
                f"{incident_by_id[incident_id]['barangay_name']}"
            ),
            key="incident_operations_select",
        )

        selected = incident_by_id[selected_id]

        render_dashboard_section_header(
            title=(
                f"{selected['control_number']} — "
                f"{selected['incident_type']}"
            ),
            subtitle=(
                f"{selected['barangay_name']} · "
                f"{selected['exact_location']} · "
                f"reported {format_datetime(selected['reported_at'])}"
            ),
        )

        render_kpi_grid(
            [
                {
                    "label": "Priority",
                    "value": str(selected["priority"]),
                },
                {
                    "label": "Status",
                    "value": str(selected["status"]),
                },
                {
                    "label": "Persons Affected",
                    "value": f"{int(selected['persons_affected']):,}",
                },
                {
                    "label": "Report Age",
                    "value": format_age(selected["reported_at"]),
                },
            ]
        )

        st.write(
            "**Description:**",
            selected["description"],
        )
        st.write(
            "**Information source:**",
            selected["source"],
        )
        st.write(
            "**Latest action / notes:**",
            selected["action_taken"]
            or "No action notes yet.",
        )

        assignments = list_incident_assignments(
            incident_id=selected_id
        )

        render_dashboard_section_header(
            title="Response Coordination",
            subtitle=(
                "Review active assignments, dispatch an available response "
                "resource, or release a resource when its incident task is complete."
            ),
        )

        if assignments:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Code": row["resource_code"],
                            "Resource": row["resource_name"],
                            "Type": row["resource_type"],
                            "Subtype": row["subtype"] or "—",
                            "Assigned": format_datetime(
                                row["assigned_at"]
                            ),
                            "Notes": row["notes"] or "—",
                        }
                        for row in assignments
                    ]
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "Code": st.column_config.TextColumn(
                        "Code",
                        width=90,
                        pinned=True,
                    ),
                    "Resource": st.column_config.TextColumn(
                        "Resource",
                        width=180,
                    ),
                    "Type": st.column_config.TextColumn(
                        "Type",
                        width=110,
                    ),
                    "Subtype": st.column_config.TextColumn(
                        "Subtype",
                        width=120,
                    ),
                    "Assigned": st.column_config.TextColumn(
                        "Assigned",
                        width=155,
                    ),
                    "Notes": st.column_config.TextColumn(
                        "Notes",
                        width=220,
                    ),
                },
            )

        available_resources = [
            resource
            for resource in resources
            if (
                resource["is_active"]
                and resource["status"] == "Available"
            )
        ]

        if selected["status"] in {"Resolved", "Cancelled"}:
            if not assignments:
                st.info(
                    "No active response resources are assigned."
                )
        elif registered_resource_count == 0:
            st.info(
                "No response resources are registered or assigned. Add a "
                "resource in Response Resources before dispatching."
            )
        elif not active_resources:
            st.warning(
                "Response resources are registered, but none are active "
                "or available for dispatch."
            )
        elif not available_resources and not assignments:
            st.warning(
                f"{len(active_resources)} active response resource(s) are "
                "registered, but none are assigned or currently Available. "
                "Review Readiness Status before dispatching."
            )
        else:
            if not assignments:
                st.info(
                    "No active response resources are assigned to this incident."
                )

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
                    st.warning(
                        f"{len(active_resources)} active response "
                        "resource(s) are registered, but none are "
                        "currently Available. Review Readiness Status "
                        "or release an assigned resource."
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

        render_dashboard_section_header(
            title="Incident Lifecycle",
            subtitle=(
                "Record forward status changes and priority adjustments. "
                "Each change is preserved in incident history."
            ),
        )

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

            priority_change_pending = (
                new_priority != str(selected["priority"])
            )
            if not priority_change_pending:
                st.caption(
                    "Select a different priority to apply a change."
                )

            if st.button(
                "Apply Priority Change",
                key=f"priority_button_{selected_id}",
                disabled=not priority_change_pending,
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
    render_dashboard_section_header(
        title="Response Resource Readiness",
        subtitle=(
            "Maintain the response-resource registry and current readiness "
            "state used for incident dispatch."
        ),
    )

    render_kpi_grid(
        [
            {
                "label": "Resources Registered",
                "value": registered_resource_count,
                "meta": (
                    f"{len(active_resources)} active"
                    if registered_resource_count
                    else "Registry not set up"
                ),
            },
            {
                "label": "Available",
                "value": available_resource_count,
            },
            {
                "label": "Assigned",
                "value": assigned_resource_count,
            },
            {
                "label": "Unavailable",
                "value": sum(
                    1
                    for resource in active_resources
                    if resource["status"]
                    in {"Maintenance", "Out of Service"}
                ),
            },
        ]
    )

    create_tab, readiness_tab = st.tabs(
        (
            "Add Resource",
            "Readiness Status",
        )
    )

    with create_tab:
        render_dashboard_section_header(
            title="Add Response Resource",
            subtitle=(
                "Create an official response-team, vehicle, or equipment record "
                "for operational dispatch."
            ),
        )

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
                width="stretch",
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
        if registered_resource_count == 0:
            st.info(
                "No response resources have been registered. Use Add "
                "Resource to create the first dispatchable record."
            )
        elif not active_resources:
            st.warning(
                "Response resources are registered, but none are active. "
                "Inactive records are retained for history and cannot be "
                "dispatched or updated here."
            )
        else:
            render_dashboard_section_header(
                title="Resource Status Board",
                subtitle=(
                    "Scan current readiness before assigning assets to incidents."
                ),
            )

            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Code": resource["resource_code"],
                            "Resource": resource["name"],
                            "Type": resource["resource_type"],
                            "Subtype": resource["subtype"] or "—",
                            "Status": resource["status"],
                            "Details": resource["details"] or "—",
                        }
                        for resource in resources
                        if resource["is_active"]
                    ]
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "Code": st.column_config.TextColumn(
                        "Code",
                        width=90,
                        pinned=True,
                    ),
                    "Resource": st.column_config.TextColumn(
                        "Resource",
                        width=180,
                    ),
                    "Type": st.column_config.TextColumn(
                        "Type",
                        width=110,
                    ),
                    "Subtype": st.column_config.TextColumn(
                        "Subtype",
                        width=120,
                    ),
                    "Status": st.column_config.TextColumn(
                        "Status",
                        width=110,
                    ),
                    "Details": st.column_config.TextColumn(
                        "Details",
                        width=260,
                    ),
                },
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
    render_dashboard_section_header(
        title="Incident Audit History",
        subtitle=(
            "Inspect the immutable operational timeline for status, priority, "
            "resource, and administrative changes."
        ),
    )

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
                            "When": format_datetime(
                                row["effective_at"]
                            ),
                            "Change": row["change_type"],
                            "Notes": row["notes"] or "—",
                            "Field": row["field_name"] or "—",
                            "Previous": row["previous_value"] or "—",
                            "New": row["new_value"] or "—",
                            "Changed By": row["changed_by"] or "—",
                        }
                        for row in history_rows
                    ]
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "When": st.column_config.TextColumn(
                        "When",
                        width=155,
                    ),
                    "Change": st.column_config.TextColumn(
                        "Change",
                        width=115,
                    ),
                    "Notes": st.column_config.TextColumn(
                        "Notes",
                        width=420,
                    ),
                    "Field": st.column_config.TextColumn(
                        "Field",
                        width=80,
                    ),
                    "Previous": st.column_config.TextColumn(
                        "Previous",
                        width=95,
                    ),
                    "New": st.column_config.TextColumn(
                        "New",
                        width=95,
                    ),
                    "Changed By": st.column_config.TextColumn(
                        "Changed By",
                        width=150,
                    ),
                },
            )
