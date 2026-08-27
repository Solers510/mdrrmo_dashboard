import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from config.access_control import PERMISSION_MANAGE_EVENTS, ROLE_ADMINISTRATOR
from config.constants import EOC_STATUSES, TROPICAL_CYCLONE_CLASSIFICATIONS
from database.models import HazardCategory, EOCAlertLevel
from services.event_service import (
    ActiveEventAlreadyExistsError, EventAuthorizationError, EventDataIntegrityError,
    EventServiceError, EventStateError, EventValidationError, change_eoc_status,
    change_event_alert, close_event, create_event, get_active_event_summary,
    get_event_history, list_alert_levels, list_recent_events, reopen_event, update_event_details,
)
from utils.auth import require_permission
from utils.ui import render_event_control_strip, render_operational_page_header
from utils.formatting import (
    format_datetime, format_age, format_report_age, format_table_age,
    display_event_name, display_sitrep, counted_label
)

# --- SETUP & CONSTANTS ---
current_user = require_permission(PERMISSION_MANAGE_EVENTS)
MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

HAZARD_CATEGORIES = [e.value for e in HazardCategory]
ALERT_LEVELS = [e.value for e in EOCAlertLevel]
LISTO_LEVELS = ["Not Applicable", "Alpha", "Bravo", "Charlie"]


# --- HELPER FUNCTIONS ---

def combine_manila(date_value: Any, time_value: Any) -> datetime:
    return datetime.combine(date_value, time_value).replace(tzinfo=MANILA_TIMEZONE)


def show_service_error(error: Exception) -> None:
    st.error(str(error))


# --- RENDERER FUNCTIONS ---

def render_no_active_event_tabs(recent_events: list[dict[str, Any]], now: datetime) -> None:
    create_tab, reopen_tab = st.tabs(("Create New Event", "Reopen Closed Event"))

    with create_tab:
        st.subheader("Create Active Event")
        event_name = st.text_input("Event name *", placeholder="Example: Luis",
                                   help="For a named tropical cyclone, enter the name only. Its current classification is stored separately.",
                                   key="new_event_name")

        col1, col2 = st.columns(2)
        with col1:
            hazard_category = st.selectbox("Hazard Category *", options=HAZARD_CATEGORIES, key="new_event_category")
        with col2:
            hazard_type = st.text_input("Specific Hazard Type *", placeholder="e.g., Tropical Cyclone, Earthquake",
                                        key="new_event_hazard")

        classification = None
        listo_cpa_level = None

        if hazard_category == HazardCategory.HYDROMETEOROLOGICAL.value:
            st.caption("Hydrometeorological Tracking")
            hm_col1, hm_col2 = st.columns(2)
            with hm_col1:
                classification = st.selectbox("Classification",
                                              options=["Not Applicable"] + TROPICAL_CYCLONE_CLASSIFICATIONS,
                                              key="new_event_classification")
            with hm_col2:
                listo_cpa_level = st.selectbox("Operation L!STO CPA", options=LISTO_LEVELS, key="new_event_listo")

        col3, col4 = st.columns(2)
        with col3:
            selected_alert_label = st.selectbox("Initial alert level *", options=ALERT_LEVELS, key="new_event_alert")
        with col4:
            eoc_status = st.selectbox("EOC status *", options=EOC_STATUSES, key="new_event_eoc")

        time_columns = st.columns(2)
        with time_columns[0]:
            start_date = st.date_input("Start date *", value=now.date(), key="new_event_date")
        with time_columns[1]:
            start_time = st.time_input("Start time *", value=now.time().replace(second=0, microsecond=0, tzinfo=None),
                                       key="new_event_time")

        sitrep = st.text_input("Current SitRep number", key="new_event_sitrep")
        official_reference = st.text_input("Official event reference", key="new_event_reference")
        overview = st.text_area("Initial situation overview", height=130, key="new_event_overview")
        initial_reason = st.text_area("Reason for initial alert level *", height=100, key="new_event_reason")
        authority = st.text_input("Declaring authority or reference", key="new_event_authority")
        confirmation = st.checkbox("I confirm that this reflects the authorized operational record.",
                                   key="new_event_confirm")

        if st.button("Create Active Event", type="primary", width="stretch", disabled=not confirmation,
                     key="new_event_submit"):
            try:
                # Clean up "Not Applicable" selections before submitting to database
                final_classification = classification if classification != "Not Applicable" else None
                final_listo = listo_cpa_level if listo_cpa_level != "Not Applicable" else None

                event_id = create_event(
                    event_name=event_name, hazard_category=hazard_category, hazard_type=hazard_type,
                    classification=final_classification, alert_code=selected_alert_label,
                    eoc_status=eoc_status, listo_cpa_level=final_listo,
                    started_at=combine_manila(start_date, start_time), current_sitrep_number=sitrep,
                    official_reference=official_reference, situation_overview=overview,
                    initial_alert_reason=initial_reason, authority_reference=authority, actor_user_id=current_user.id,
                )
            except (EventValidationError, EventAuthorizationError, EventDataIntegrityError,
                    ActiveEventAlreadyExistsError, EventServiceError) as error:
                show_service_error(error)
            else:
                st.session_state["event_control_success"] = f"Event #{event_id} was created successfully."
                st.rerun()

    with reopen_tab:
        if current_user.role != ROLE_ADMINISTRATOR:
            st.info("Only an Administrator may reopen a closed event.")
        else:
            closed_events = [row for row in recent_events if not row["is_active"]]
            if not closed_events:
                st.info("No closed events are available to reopen.")
            else:
                event_by_id = {int(row["id"]): row for row in closed_events}
                selected_id = st.selectbox("Closed event", options=list(event_by_id.keys()), format_func=lambda
                    e_id: f"#{e_id} — {display_event_name(event_by_id[e_id])}", key="reopen_event_id")
                reason = st.text_area("Reason for reopening *", key="reopen_reason")
                reference = st.text_input("Authority or reference", key="reopen_reference")
                confirm_reopen = st.checkbox("I understand that reopening restores this as the active event.",
                                             key="reopen_confirm")

                if st.button("Reopen Event", disabled=not confirm_reopen, key="reopen_submit"):
                    try:
                        reopen_event(event_id=int(selected_id), reason=reason, authority_reference=reference,
                                     actor_user_id=current_user.id)
                    except EventServiceError as error:
                        show_service_error(error)
                    else:
                        st.session_state["event_control_success"] = f"Event #{selected_id} was reopened."
                        st.rerun()


def render_active_event_tabs(active_event: dict[str, Any], history: list[dict[str, Any]], now: datetime) -> None:
    overview_tab, details_tab, operations_tab, history_tab, close_tab = st.tabs(
        ("Overview", "Update Details", "Alert & EOC", "History", "Close Event"))

    with overview_tab:
        st.write("**Hazard Category:**", str(active_event.get("hazard_category", "Not set")))
        st.write("**Specific Hazard:**", str(active_event.get("hazard_type", "Not set")))
        if active_event.get("listo_cpa_level"):
            st.write("**Operation L!STO:**", str(active_event["listo_cpa_level"]))
        st.write("**SitRep:**", active_event["current_sitrep_number"] or "Not provided")
        st.write("**Official reference:**", active_event["official_reference"] or "Not provided")
        st.write("**Situation overview:**", active_event["situation_overview"] or "No overview entered.")
        st.info(
            "Event name, cyclone classification, SitRep, reference, and overview can be updated without creating a new event.")

    with details_tab:
        edit_name = st.text_input("Event name *", value=str(active_event["event_name"]), key="edit_event_name")

        edit_classification = active_event.get("classification")
        if active_event.get("hazard_category") == HazardCategory.HYDROMETEOROLOGICAL.value:
            current_classification = active_event.get("classification")
            default_index = TROPICAL_CYCLONE_CLASSIFICATIONS.index(
                current_classification) if current_classification in TROPICAL_CYCLONE_CLASSIFICATIONS else 0
            edit_classification = st.selectbox("Current classification *", options=TROPICAL_CYCLONE_CLASSIFICATIONS,
                                               index=default_index, key="edit_classification")

        edit_sitrep = st.text_input("Current SitRep number", value=active_event["current_sitrep_number"] or "",
                                    key="edit_sitrep")
        edit_reference = st.text_input("Official event reference", value=active_event["official_reference"] or "",
                                       key="edit_reference")
        edit_overview = st.text_area("Situation overview", value=active_event["situation_overview"] or "", height=150,
                                     key="edit_overview")
        edit_reason = st.text_area("Reason for change *", key="edit_reason")
        edit_authority = st.text_input("Authority or supporting reference", key="edit_authority")

        if st.button("Save Event Details", type="primary", key="edit_submit"):
            try:
                update_event_details(
                    event_id=int(active_event["id"]), event_name=edit_name, classification=edit_classification,
                    current_sitrep_number=edit_sitrep, official_reference=edit_reference,
                    situation_overview=edit_overview,
                    reason=edit_reason, authority_reference=edit_authority, actor_user_id=current_user.id,
                )
            except EventServiceError as error:
                show_service_error(error)
            else:
                st.session_state["event_control_success"] = "Event details updated."
                st.rerun()

    with operations_tab:
        st.markdown("### Change alert level")
        current_alert_index = ALERT_LEVELS.index(str(active_event["alert_level"])) if str(
            active_event.get("alert_level")) in ALERT_LEVELS else 0
        new_alert_label = st.selectbox("New alert level", options=ALERT_LEVELS, index=current_alert_index,
                                       key="change_alert_label")

        alert_time_columns = st.columns(2)
        with alert_time_columns[0]:
            alert_date = st.date_input("Alert effective date", value=now.date(), key="change_alert_date")
        with alert_time_columns[1]:
            alert_time = st.time_input("Alert effective time",
                                       value=now.time().replace(second=0, microsecond=0, tzinfo=None),
                                       key="change_alert_time")

        alert_reason = st.text_area("Reason for alert change *", key="change_alert_reason")
        alert_reference = st.text_input("Alert authority/reference", key="change_alert_reference")

        if st.button("Apply Alert Change", type="primary", key="alert_submit"):
            try:
                change_event_alert(
                    event_id=int(active_event["id"]), new_alert_code=new_alert_label,
                    effective_at=combine_manila(alert_date, alert_time), reason=alert_reason,
                    authority_reference=alert_reference, actor_user_id=current_user.id,
                )
            except EventServiceError as error:
                show_service_error(error)
            else:
                st.session_state["event_control_success"] = "Alert level updated."
                st.rerun()

        st.divider()
        st.markdown("### Change EOC status")
        current_eoc_index = EOC_STATUSES.index(str(active_event["eoc_status"])) if str(
            active_event.get("eoc_status")) in EOC_STATUSES else 0
        new_eoc = st.selectbox("New EOC status", options=EOC_STATUSES, index=current_eoc_index, key="change_eoc_status")
        eoc_reason = st.text_area("Reason for EOC-status change *", key="change_eoc_reason")
        eoc_reference = st.text_input("EOC authority/reference", key="change_eoc_reference")

        if st.button("Apply EOC Change", key="eoc_submit"):
            try:
                change_eoc_status(
                    event_id=int(active_event["id"]), new_status=new_eoc, reason=eoc_reason,
                    authority_reference=eoc_reference, actor_user_id=current_user.id,
                )
            except EventServiceError as error:
                show_service_error(error)
            else:
                st.session_state["event_control_success"] = "EOC status updated."
                st.rerun()

    with history_tab:
        if not history:
            st.info("No event-change history is available yet.")
        else:
            st.dataframe(pd.DataFrame([
                {"When": row["effective_at"], "Change": row["change_type"], "Field": row["field_name"],
                 "Previous": row["previous_value"], "New": row["new_value"], "Reason": row["reason"],
                 "Authority/Reference": row["authority_reference"], "Changed By": row["changed_by"]}
                for row in history
            ]), width="stretch", hide_index=True)

    with close_tab:
        st.warning(
            "Closing the event stops new barangay and evacuation-center reports until another event is created or an Administrator reopens this event.")
        close_time_columns = st.columns(2)
        with close_time_columns[0]:
            end_date = st.date_input("End date *", value=now.date(), key="close_date")
        with close_time_columns[1]:
            end_time = st.time_input("End time *", value=now.time().replace(second=0, microsecond=0, tzinfo=None),
                                     key="close_time")

        close_reason = st.text_area("Reason for closing event *", key="close_reason")
        close_reference = st.text_input("Authority/reference", key="close_reference")
        close_confirm = st.checkbox("I confirm that operational reporting for this event should stop.",
                                    key="close_confirm")

        if st.button("Close Active Event", disabled=not close_confirm, key="close_submit"):
            try:
                close_event(
                    event_id=int(active_event["id"]), ended_at=combine_manila(end_date, end_time),
                    reason=close_reason, authority_reference=close_reference, actor_user_id=current_user.id,
                )
            except EventServiceError as error:
                show_service_error(error)
            else:
                st.session_state["event_control_success"] = "Event closed successfully."
                st.rerun()


# --- MAIN EXECUTION BLOCK ---

render_operational_page_header(title="Event Control",
                               subtitle="Create, update, escalate, stand down, close, and audit the current disaster event.")

success_message = st.session_state.pop("event_control_success", None)
if success_message: st.success(success_message)

try:
    active_event = get_active_event_summary()
    recent_events = list_recent_events(limit=20)
except EventServiceError as error:
    show_service_error(error)
    st.stop()
except Exception:
    st.error("Event Control could not retrieve operational data.")
    st.stop()

now = datetime.now(MANILA_TIMEZONE)

if active_event is None:
    render_no_active_event_tabs(recent_events, now)
    st.stop()

render_event_control_strip(
    event_name=display_event_name(active_event), hazard_type=str(active_event["hazard_type"]),
    classification = st.selectbox("Classification",
    options=["Not Applicable"] + list(TROPICAL_CYCLONE_CLASSIFICATIONS), key="new_event_classification"),
    alert_code=str(active_event["alert_level"]), eoc_status=str(active_event["eoc_status"]),
    sitrep=str(active_event["current_sitrep_number"] or "Not provided"),
    started_at=format_datetime(active_event["started_at"]),
    official_reference=str(active_event["official_reference"]) if active_event["official_reference"] else None,
)

try:
    history = get_event_history(event_id=int(active_event["id"]), limit=100)
except EventServiceError:
    history = []

render_active_event_tabs(active_event, history, now)