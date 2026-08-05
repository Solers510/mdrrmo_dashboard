import streamlit as st


st.title("MDRRMO Naic Situation Dashboard")

st.caption(
    "Current disaster situation, operational readiness, "
    "evacuation figures, incidents, and response resources."
)

st.info(
    "The database and live dashboard calculations will be "
    "connected in the next phases."
)

column_1, column_2, column_3, column_4 = st.columns(4)

with column_1:
    st.metric(
        label="Affected Barangays",
        value=0,
    )

with column_2:
    st.metric(
        label="Affected Families",
        value=0,
    )

with column_3:
    st.metric(
        label="Affected Individuals",
        value=0,
    )

with column_4:
    st.metric(
        label="Active Incidents",
        value=0,
    )

st.subheader("Operational Status")

st.write(
    "No active disaster-event data is currently connected."
)