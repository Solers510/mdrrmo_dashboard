import streamlit as st

from config.access_control import (
    PERMISSION_MANAGE_EVENTS,
    PERMISSION_MANAGE_EVACUATION_CENTERS,
    PERMISSION_MANAGE_INCIDENTS,
    PERMISSION_SUBMIT_BARANGAY_UPDATES,
    PERMISSION_SUBMIT_EVACUATION_UPDATES,
    PERMISSION_VALIDATE_BARANGAY_REPORTS,
    PERMISSION_VIEW_DASHBOARD,
    PERMISSION_VIEW_REPORTS,
)
from utils.auth import (
    get_current_app_user,
    has_any_permission,
    has_permission,
    login_screen,
    render_account_sidebar,
)


st.set_page_config(
    page_title="MDRRMO Naic Dashboard",
    layout="wide",
)


if not getattr(
    st.user,
    "is_logged_in",
    False,
):
    login_screen()


current_user = get_current_app_user()

render_account_sidebar(
    current_user
)


dashboard_page = st.Page(
    "pages/dashboard.py",
    title="Dashboard",
    default=True,
)

event_control_page = st.Page(
    "pages/event_control.py",
    title="Event Control",
)

barangay_updates_page = st.Page(
    "pages/barangay_updates.py",
    title="Barangay Updates",
)

validation_page = st.Page(
    "pages/validation.py",
    title="Report Validation",
)

evacuation_centers_page = st.Page(
    "pages/evacuation_centers.py",
    title="Evacuation Centers",
)

incidents_page = st.Page(
    "pages/incidents.py",
    title="Incidents",
)

reports_page = st.Page(
    "pages/reports.py",
    title="Reports",
)


operations_pages = []

if has_permission(
    current_user,
    PERMISSION_VIEW_DASHBOARD,
):
    operations_pages.append(
        dashboard_page
    )

if has_permission(
    current_user,
    PERMISSION_MANAGE_EVENTS,
):
    operations_pages.append(
        event_control_page
    )

if has_permission(
    current_user,
    PERMISSION_SUBMIT_BARANGAY_UPDATES,
):
    operations_pages.append(
        barangay_updates_page
    )

if has_permission(
    current_user,
    PERMISSION_VALIDATE_BARANGAY_REPORTS,
):
    operations_pages.append(
        validation_page
    )

if has_any_permission(
    current_user,
    PERMISSION_MANAGE_EVACUATION_CENTERS,
    PERMISSION_SUBMIT_EVACUATION_UPDATES,
):
    operations_pages.append(
        evacuation_centers_page
    )

if has_permission(
    current_user,
    PERMISSION_MANAGE_INCIDENTS,
):
    operations_pages.append(
        incidents_page
    )


navigation_sections = {}

if operations_pages:
    navigation_sections[
        "Operations"
    ] = operations_pages


if has_permission(
    current_user,
    PERMISSION_VIEW_REPORTS,
):
    navigation_sections[
        "Reporting"
    ] = [
        reports_page,
    ]


if not navigation_sections:
    st.error(
        "Your role has no assigned application pages."
    )
    st.stop()


selected_page = st.navigation(
    navigation_sections
)

selected_page.run()