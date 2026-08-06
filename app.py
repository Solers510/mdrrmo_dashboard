import streamlit as st


st.set_page_config(
    page_title="MDRRMO Naic Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


pages = {
    "Operations": [
        st.Page(
            "pages/dashboard.py",
            title="Dashboard",
            default=True,
        ),
        st.Page(
            "pages/event_control.py",
            title="Event Control",
        ),
        st.Page(
            "pages/barangay_updates.py",
            title="Barangay Updates",
        ),
        st.Page(
            "pages/validation.py",
            title="Report Validation",
        ),
        st.Page(
            "pages/evacuation_centers.py",
            title="Evacuation Centers",
        ),
        st.Page(
            "pages/incidents.py",
            title="Incidents",
        ),
    ],
    "Reporting": [
        st.Page(
            "pages/reports.py",
            title="Reports",
        ),
    ],
}


with st.sidebar:
    st.markdown("## MDRRMO Naic")
    st.caption("Disaster Monitoring and Reporting System")


navigation = st.navigation(pages)
navigation.run()