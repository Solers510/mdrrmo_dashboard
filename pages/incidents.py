import streamlit as st
from config.access_control import (
    PERMISSION_MANAGE_INCIDENTS,
)
from utils.auth import require_permission


current_user = require_permission(
    PERMISSION_MANAGE_INCIDENTS
)

st.title("Incident Monitoring")

st.caption(
    "Record incidents, requests for assistance, response "
    "assignments, and status changes."
)

with st.form("incident_form"):
    barangay = st.text_input("Barangay")

    exact_location = st.text_input(
        "Exact location or landmark"
    )

    incident_type = st.selectbox(
        "Incident type",
        [
            "Flooding",
            "Rescue Request",
            "Medical Emergency",
            "Fallen Tree",
            "Road Obstruction",
            "Structural Damage",
            "Power Interruption",
            "Water Interruption",
            "Landslide",
            "Maritime Incident",
            "Missing Person",
            "Other",
        ],
    )

    priority = st.selectbox(
        "Priority",
        [
            "Low",
            "Moderate",
            "High",
            "Critical",
        ],
    )

    description = st.text_area("Incident description")

    status = st.selectbox(
        "Status",
        [
            "Reported",
            "For Verification",
            "Verified",
            "Team Dispatched",
            "Responding",
            "Resolved",
            "Cancelled",
        ],
    )

    source = st.text_input("Information source")

    submitted = st.form_submit_button(
        "Save Incident",
        type="primary",
    )

if submitted:
    if not exact_location.strip():
        st.error("The incident location is required.")
    elif not description.strip():
        st.error("An incident description is required.")
    elif not source.strip():
        st.error("An information source is required.")
    else:
        st.warning(
            "The incident passed validation, but database "
            "storage is not yet connected."
        )