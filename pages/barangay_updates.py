import streamlit as st


st.title("Barangay Situation Update")

st.caption(
    "Record the latest situation reported by each barangay."
)

with st.form("barangay_update_form"):
    barangay = st.selectbox(
        "Barangay",
        [
            "Bagong Karsada",
            "Balsahan",
            "Bancaan",
            "Bucana Malaki",
            "Bucana Sasahan",
            "Sabang",
        ],
    )

    situation_status = st.selectbox(
        "Situation status",
        [
            "No Report",
            "Normal",
            "Monitoring",
            "Affected",
            "Critical",
        ],
    )

    affected_families = st.number_input(
        "Affected families",
        min_value=0,
        step=1,
    )

    affected_individuals = st.number_input(
        "Affected individuals",
        min_value=0,
        step=1,
    )

    source = st.text_input(
        "Information source",
        placeholder="Barangay official, responder, radio, etc.",
    )

    confirmation_status = st.selectbox(
        "Confirmation status",
        [
            "Unconfirmed",
            "Confirmed",
        ],
    )

    remarks = st.text_area("Remarks")

    submitted = st.form_submit_button(
        "Save Barangay Update",
        type="primary",
    )

if submitted:
    if not source.strip():
        st.error("An information source is required.")
    elif affected_individuals < affected_families:
        st.warning(
            "Affected individuals are lower than affected "
            "families. Confirm whether the figures are correct."
        )
    else:
        st.warning(
            "The form passed validation, but database storage "
            "is not yet connected."
        )