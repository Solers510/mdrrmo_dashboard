import streamlit as st


st.title("Event Control")

st.caption(
    "Create and manage disaster events, alert levels, "
    "EOC status, and official reporting periods."
)

with st.form("event_control_form"):
    event_name = st.text_input(
        "Event name",
        placeholder="Example: Tropical Depression Luis",
    )

    hazard_type = st.selectbox(
        "Hazard type",
        [
            "Tropical Cyclone",
            "Flood",
            "Earthquake",
            "Fire",
            "Landslide",
            "Other",
        ],
    )

    alert_level = st.selectbox(
        "Alert level",
        [
            "WHITE",
            "BLUE",
            "RED",
        ],
    )

    eoc_status = st.selectbox(
        "EOC status",
        [
            "Monitoring",
            "Partially Activated",
            "Activated",
            "Stand Down",
        ],
    )

    situation_overview = st.text_area(
        "Situation overview",
        placeholder="Enter a brief operational summary.",
    )

    submitted = st.form_submit_button(
        "Save Event",
        type="primary",
    )

if submitted:
    if not event_name.strip():
        st.error("Event name is required.")
    else:
        st.warning(
            "The form is working, but database storage "
            "has not yet been connected."
        )