import streamlit as st


st.title("Evacuation Center Monitoring")

st.caption(
    "Record center status, occupancy, vulnerable groups, "
    "and essential services."
)

with st.form("evacuation_center_form"):
    center_name = st.text_input("Evacuation center name")

    barangay = st.text_input("Barangay")

    center_status = st.selectbox(
        "Center status",
        [
            "Standby",
            "Open",
            "Full",
            "Over Capacity",
            "Closed",
        ],
    )

    capacity = st.number_input(
        "Safe capacity",
        min_value=0,
        step=1,
    )

    families = st.number_input(
        "Current families",
        min_value=0,
        step=1,
    )

    individuals = st.number_input(
        "Current individuals",
        min_value=0,
        step=1,
    )

    food_status = st.selectbox(
        "Food status",
        [
            "Unknown",
            "Sufficient",
            "Low",
            "Critical",
            "Unavailable",
        ],
    )

    water_status = st.selectbox(
        "Water status",
        [
            "Unknown",
            "Sufficient",
            "Low",
            "Critical",
            "Unavailable",
        ],
    )

    source = st.text_input("Information source")

    submitted = st.form_submit_button(
        "Save Evacuation Update",
        type="primary",
    )

if submitted:
    if not center_name.strip():
        st.error("Evacuation center name is required.")
    elif not source.strip():
        st.error("Information source is required.")
    else:
        st.warning(
            "The form is ready, but database storage "
            "has not yet been connected."
        )