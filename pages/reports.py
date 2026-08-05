import streamlit as st


st.title("Reports and Exports")

st.caption(
    "Generate situation reports, incident logs, barangay "
    "summaries, and evacuation-center reports."
)

st.info(
    "Excel and PDF export functions will be added after "
    "the database and dashboard calculations are complete."
)

st.button(
    "Generate Excel Report",
    disabled=True,
)

st.button(
    "Generate PDF SitRep",
    disabled=True,
)