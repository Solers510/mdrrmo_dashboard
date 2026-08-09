import streamlit as st
from config.access_control import (
    PERMISSION_VIEW_REPORTS,
)
from utils.auth import require_permission


current_user = require_permission(
    PERMISSION_VIEW_REPORTS
)

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