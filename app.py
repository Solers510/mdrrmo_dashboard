import streamlit as st

from config.access_control import (
    PERMISSION_MANAGE_EVENTS,
    PERMISSION_MANAGE_EVACUATION_CENTERS,
    PERMISSION_MANAGE_INCIDENTS,
    PERMISSION_MANAGE_USERS,
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
from utils.ui import (
    load_design_system,
    render_sidebar_brand,
)


st.set_page_config(
    page_title="OMDRRMO Naic Operations",
    layout="wide",
)

load_design_system()


if not getattr(st.user, "is_logged_in", False):
    login_screen()


current_user = get_current_app_user(
    refresh_authorization=True
)

render_sidebar_brand()
render_account_sidebar(current_user)


dashboard_page = st.Page(
    "pages/dashboard.py",
    title="Dashboard",
    icon=":material/dashboard:",
    default=True,
)
event_control_page = st.Page(
    "pages/event_control.py",
    title="Event Control",
    icon=":material/event:",
)
barangay_updates_page = st.Page(
    "pages/barangay_updates.py",
    title="Barangay Updates",
    icon=":material/edit_note:",
)
validation_page = st.Page(
    "pages/validation.py",
    title="Report Validation",
    icon=":material/fact_check:",
)
evacuation_centers_page = st.Page(
    "pages/evacuation_centers.py",
    title="Evacuation Centers",
    icon=":material/apartment:",
)
incidents_page = st.Page(
    "pages/incidents.py",
    title="Incidents",
    icon=":material/emergency:",
)
reports_page = st.Page(
    "pages/reports.py",
    title="Reports",
    icon=":material/description:",
)
user_admin_page = st.Page(
    "pages/user_admin.py",
    title="User Administration",
    icon=":material/manage_accounts:",
)
system_admin_page = st.Page(
    "pages/system_admin.py",
    title="System Health & Audit",
    icon=":material/monitoring:",
)


operations_pages = []

if has_permission(current_user, PERMISSION_VIEW_DASHBOARD):
    operations_pages.append(dashboard_page)

if has_permission(current_user, PERMISSION_MANAGE_EVENTS):
    operations_pages.append(event_control_page)

if has_permission(
    current_user,
    PERMISSION_SUBMIT_BARANGAY_UPDATES,
):
    operations_pages.append(barangay_updates_page)

if has_permission(
    current_user,
    PERMISSION_VALIDATE_BARANGAY_REPORTS,
):
    operations_pages.append(validation_page)

if has_any_permission(
    current_user,
    PERMISSION_MANAGE_EVACUATION_CENTERS,
    PERMISSION_SUBMIT_EVACUATION_UPDATES,
):
    operations_pages.append(evacuation_centers_page)

if has_permission(current_user, PERMISSION_MANAGE_INCIDENTS):
    operations_pages.append(incidents_page)


navigation_sections = {}

if operations_pages:
    navigation_sections["Operations"] = operations_pages

if has_permission(current_user, PERMISSION_VIEW_REPORTS):
    navigation_sections["Reporting"] = [reports_page]

if has_permission(current_user, PERMISSION_MANAGE_USERS):
    navigation_sections["Administration"] = [user_admin_page, system_admin_page]

if not navigation_sections:
    st.error("Your role has no assigned application pages.")
    st.stop()


selected_page = st.navigation(navigation_sections)
selected_page.run()
