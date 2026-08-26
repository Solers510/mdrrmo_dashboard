import pandas as pd
import streamlit as st
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from typing import Any

from config.access_control import PERMISSION_SUBMIT_BARANGAY_UPDATES
from config.constants import FLOOD_STATUSES, ROAD_STATUSES, SITUATION_STATUSES, UTILITY_STATUSES
from services.barangay_service import (
    BarangayDataIntegrityError, BarangayServiceError, BarangayValidationError,
    DuplicateBarangaySubmissionError, NoActiveEventError, create_barangay_update,
    get_barangay_entry_context, get_pending_barangay_correction, get_recent_barangay_updates,
    list_active_barangays,
)
from services.data_integrity import DataIntegrityValidationError, reconcile_population, validate_flood_consistency
from services.event_service import EventDataIntegrityError, get_active_event_summary
from utils.auth import require_permission
from utils.ui import (
    render_dashboard_section_header, render_kpi_grid, render_operational_event_strip,
    render_operational_page_header, render_workflow_section,
)
from utils.formatting import format_datetime, format_report_age, display_event_name, display_sitrep, select_index
current_user = require_permission(PERMISSION_SUBMIT_BARANGAY_UPDATES)
MANILA_TIMEZONE = ZoneInfo("Asia/Manila")



def render_recent_updates_section(recent_updates: list[dict[str, Any]]) -> None:
    render_dashboard_section_header(
        title="Recent Barangay Reports",
        subtitle="Recent submissions for the active event, including validation status and source timing.",
    )

    if not recent_updates:
        st.info("No barangay reports have been recorded for the active event.")
        return

    routine_rows = [
        {
            "Report": int(row["id"]),
            "Barangay": row["barangay_name"],
            "Situation": row["situation_status"],
            "Affected F / I": f"{int(row['affected_families']):,} / {int(row['affected_individuals']):,}",
            "Displaced Individuals": int(row["inside_ec_individuals"]) + int(row["outside_ec_individuals"]),
            "Rescue": int(row["rescue_requests"]),
            "Validation": row["validation_status"],
            "Age": format_report_age(row["recorded_at"]),
        } for row in recent_updates
    ]

    st.dataframe(pd.DataFrame(routine_rows), width="stretch", hide_index=True, column_order=("Report", "Barangay", "Situation", "Affected F / I", "Displaced Individuals", "Rescue", "Validation", "Age"),
    column_config={
        "Report": st.column_config.NumberColumn("#", width=55, format="%d"),
        "Barangay": st.column_config.TextColumn("Barangay", width=155, pinned=True),
        "Situation": st.column_config.TextColumn("Situation", width=95),
        "Affected F / I": st.column_config.TextColumn("Affected F / I", help="Affected families / affected individuals", width=105),
        "Displaced Individuals": st.column_config.NumberColumn("Displaced", help="Individuals inside + outside evacuation centers", width=82, format="%d"),
        "Rescue": st.column_config.NumberColumn("Rescue", width=68, format="%d"),
        "Validation": st.column_config.TextColumn("Validation", width=110),
        "Age": st.column_config.TextColumn("Age", width=60),
    })

    with st.expander("Full recent report fields", expanded=False):
        st.dataframe(pd.DataFrame([{
            "ID": r["id"], "Barangay": r["barangay_name"], "Situation": r["situation_status"],
            "Affected Families": r["affected_families"], "Affected Individuals": r["affected_individuals"],
            "Inside EC": r["inside_ec_individuals"], "Outside EC": r["outside_ec_individuals"],
            "Rescue Requests": r["rescue_requests"], "Validation": r["validation_status"],
            "Source": r["source"], "Recorded At": r["recorded_at"],
        } for r in recent_updates]), width="stretch", hide_index=True)


render_operational_page_header(
    title="Barangay Situation Update",
    subtitle="Record the latest barangay population, evacuation, access, utility, rescue, and source information for the active event.",
)

success_message = st.session_state.pop("barangay_update_success", None)
if success_message: st.success(success_message)

try:
    active_event = get_active_event_summary()
except EventDataIntegrityError as error:
    st.error(str(error))
    st.stop()
except Exception:
    st.error("The active disaster event could not be loaded.")
    st.stop()

if active_event is None:
    st.warning("No active disaster event exists. Create an event in Event Control before recording reports.")
    st.stop()

render_operational_event_strip(
    event_name=display_event_name(active_event), hazard_type=str(active_event["hazard_type"]),
    alert_code=str(active_event["alert_code"]), eoc_status=str(active_event["eoc_status"]),
    sitrep=display_sitrep(active_event), official_reference=str(active_event["official_reference"]) if active_event.get("official_reference") else None,
)

try:
    barangay_records = list_active_barangays()
except BarangayServiceError as error:
    st.error(str(error))
    st.stop()

if not barangay_records:
    st.error("No active barangays were found.")
    st.stop()

barangay_label_to_id = {f"{r['name']} — {r['psgc_code']}": int(r["id"]) for r in barangay_records}
barangay_labels = list(barangay_label_to_id)

render_dashboard_section_header(title="Submit Barangay Situation Report", subtitle=f"Submitting as {current_user.display_name} — {current_user.role}. Required fields are marked with an asterisk.")

nonce = int(st.session_state.setdefault("barangay_form_nonce", 0))
selector_key = f"barangay_{nonce}_barangay"
token_state_key = f"barangay_submission_key_{nonce}"
if token_state_key not in st.session_state: st.session_state[token_state_key] = str(uuid4())

render_workflow_section(step=1, title="Select Barangay", subtitle="Choose the reporting barangay. Form state is isolated by barangay so figures do not carry over when the selection changes.")
selected_label = st.selectbox("Barangay *", options=barangay_labels, key=selector_key)
selected_barangay_id = barangay_label_to_id[selected_label]
prefix = f"barangay_{nonce}_{selected_barangay_id}_"

try:
    entry_context = get_barangay_entry_context(barangay_id=selected_barangay_id)
    pending_correction = get_pending_barangay_correction(barangay_id=selected_barangay_id)
except BarangayServiceError as error:
    st.error(str(error))
    st.stop()

if pending_correction is not None:
    correction_id = int(pending_correction["id"])
    prefix = f"barangay_{nonce}_{selected_barangay_id}_correction_{correction_id}_"
    st.error(f"Correction Required — Barangay Report #{correction_id}")
    cols = st.columns(2)
    cols[0].write("**Reviewed by:** " + str(pending_correction["reviewed_by"] or "Authorized validator"))
    cols[1].write("**Reviewed at:** " + (format_datetime(pending_correction["reviewed_at"]) if pending_correction["reviewed_at"] else "Not recorded"))
    st.warning("**Validator instructions:** " + str(pending_correction["review_notes"] or "No correction instructions were recorded."))
    st.info(f"The form below is prefilled from Report #{correction_id}. Submitting the corrected report will supersede Report #{correction_id}; the original remains in history.")

render_workflow_section(step=2, title="Inside Evacuation Centers", subtitle="Use the latest evacuation-center figures as reference. Enter a newer verified barangay count when available; differences are flagged for reconciliation rather than blocked.")
render_kpi_grid([
    {"label": "EC Reference — Families", "value": f"{int(entry_context['inside_ec_families']):,}"},
    {"label": "EC Reference — Individuals", "value": f"{int(entry_context['inside_ec_individuals']):,}"},
    {"label": "Operational Centers", "value": f"{int(entry_context['operational_centers']):,}"},
], compact=True)
st.caption("Reference updated: " + format_datetime(entry_context["latest_ec_update"]))

cols = st.columns(2)
inside_ec_families = cols[0].number_input("Families inside EC", min_value=0, step=1, value=int(pending_correction["inside_ec_families"]) if pending_correction else int(entry_context["inside_ec_families"]), key=prefix + "inside_families")
inside_ec_individuals = cols[1].number_input("Individuals inside EC", min_value=0, step=1, value=int(pending_correction["inside_ec_individuals"]) if pending_correction else int(entry_context["inside_ec_individuals"]), key=prefix + "inside_individuals")

if int(inside_ec_families) != int(entry_context["inside_ec_families"]) or int(inside_ec_individuals) != int(entry_context["inside_ec_individuals"]):
    st.warning("The barangay Inside-EC figures differ from the latest evacuation-center records. This is allowed when the barangay has newer verified information. The difference should be checked during validation.")

render_workflow_section(step=3, title="Affected Population", subtitle="Record the total affected families and individuals for this barangay before separating displaced populations.")
cols = st.columns(2)
affected_families = cols[0].number_input("Affected families", min_value=0, step=1, value=int(pending_correction["affected_families"]) if pending_correction else 0, key=prefix + "affected_families")
affected_individuals = cols[1].number_input("Affected individuals", min_value=0, step=1, value=int(pending_correction["affected_individuals"]) if pending_correction else 0, key=prefix + "affected_individuals")

render_workflow_section(step=4, title="Outside Evacuation Centers", subtitle="Record displaced families and individuals staying outside formal evacuation centers.")
cols = st.columns(2)
outside_ec_families = cols[0].number_input("Families outside EC", min_value=0, step=1, value=int(pending_correction["outside_ec_families"]) if pending_correction else 0, key=prefix + "outside_families")
outside_ec_individuals = cols[1].number_input("Individuals outside EC", min_value=0, step=1, value=int(pending_correction["outside_ec_individuals"]) if pending_correction else 0, key=prefix + "outside_individuals")

preview_error, reconciliation = None, None
try:
    reconciliation = reconcile_population(
        affected_families=int(affected_families), affected_individuals=int(affected_individuals),
        inside_ec_families=int(inside_ec_families), inside_ec_individuals=int(inside_ec_individuals),
        outside_ec_families=int(outside_ec_families), outside_ec_individuals=int(outside_ec_individuals),
    )
except DataIntegrityValidationError as error:
    preview_error = str(error)

render_dashboard_section_header(title="Population Consistency Check", subtitle="The system verifies that displaced counts do not exceed the affected totals before submission.")
if reconciliation:
    render_kpi_grid([
        {"label": "Affected Families", "value": f"{int(affected_families):,}"}, {"label": "Displaced Families", "value": f"{int(reconciliation.displaced_families):,}"},
        {"label": "Affected Individuals", "value": f"{int(affected_individuals):,}"}, {"label": "Displaced Individuals", "value": f"{int(reconciliation.displaced_individuals):,}"},
    ])
    st.success("Displaced counts are within the affected population totals.")
else:
    st.error(preview_error)

render_workflow_section(step=5, title="Operational Conditions", subtitle="Record the current situation, flooding, road access, utilities, and any pending rescue demand.")
situation_status = st.selectbox("Situation status *", options=SITUATION_STATUSES, index=select_index(SITUATION_STATUSES, pending_correction["situation_status"], min(2, len(SITUATION_STATUSES) - 1)) if pending_correction else min(2, len(SITUATION_STATUSES) - 1), key=prefix + "situation_status")
cols = st.columns(2)
with cols[0]:
    flood_status = st.selectbox("Flood status", options=FLOOD_STATUSES, index=select_index(FLOOD_STATUSES, pending_correction["flood_status"]) if pending_correction else 0, key=prefix + "flood_status")
    flood_depth_cm = st.number_input("Estimated flood depth in centimeters", min_value=0.0, step=1.0, format="%.2f", value=float(pending_correction["flood_depth_cm"]) if pending_correction else 0.0, key=prefix + "flood_depth")
    road_status = st.selectbox("Road status", options=ROAD_STATUSES, index=select_index(ROAD_STATUSES, pending_correction["road_status"]) if pending_correction else 0, key=prefix + "road_status")
with cols[1]:
    power_status = st.selectbox("Power status", options=UTILITY_STATUSES, index=select_index(UTILITY_STATUSES, pending_correction["power_status"]) if pending_correction else 0, key=prefix + "power_status")
    water_status = st.selectbox("Water status", options=UTILITY_STATUSES, index=select_index(UTILITY_STATUSES, pending_correction["water_status"]) if pending_correction else 0, key=prefix + "water_status")
    rescue_requests = st.number_input("Pending rescue requests", min_value=0, step=1, value=int(pending_correction["rescue_requests"]) if pending_correction else 0, key=prefix + "rescue_requests")

flood_error = None
try:
    validate_flood_consistency(flood_status=flood_status, flood_depth_cm=float(flood_depth_cm))
except DataIntegrityValidationError as error:
    flood_error = str(error)
    st.error(flood_error)

render_workflow_section(step=6, title="Source & Submit", subtitle="Identify the source, add useful context, review the figures, and submit the report for validation.")
source = st.text_input("Information source *", value=str(pending_correction["source"]) if pending_correction else "", placeholder="Barangay Captain, BDRRMC radio, field responder, official report", key=prefix + "source")
remarks = st.text_area("Remarks", value=str(pending_correction["remarks"] or "") if pending_correction else "", height=120, key=prefix + "remarks")
confirmation = st.checkbox("I reviewed the figures and source before submission.", key=prefix + "confirmation")

can_submit = preview_error is None and flood_error is None and bool(source.strip()) and confirmation

if st.button("Save Barangay Report", type="primary", width="stretch", disabled=not can_submit, key=prefix + "submit"):
    try:
        update_id = create_barangay_update(
            barangay_id=selected_barangay_id, situation_status=situation_status, affected_families=int(affected_families),
            affected_individuals=int(affected_individuals), inside_ec_families=int(inside_ec_families), inside_ec_individuals=int(inside_ec_individuals),
            outside_ec_families=int(outside_ec_families), outside_ec_individuals=int(outside_ec_individuals),
            flood_status=flood_status, flood_depth_cm=float(flood_depth_cm), road_status=road_status,
            power_status=power_status, water_status=water_status, rescue_requests=int(rescue_requests),
            source=source, remarks=remarks, submission_key=st.session_state[token_state_key], submitter_user_id=current_user.id,
        )
    except (NoActiveEventError, BarangayValidationError, BarangayDataIntegrityError, DuplicateBarangaySubmissionError, BarangayServiceError) as error:
        st.error(str(error))
    except Exception:
        st.error("The report could not be saved. Your entered values were kept; try again or contact the system administrator.")
    else:
        st.session_state["barangay_update_success"] = f"Barangay report #{update_id} was saved successfully."
        st.session_state["barangay_form_nonce"] = nonce + 1
        st.session_state.pop(token_state_key, None)
        st.rerun()

st.divider()

try:
    recent_updates = get_recent_barangay_updates(limit=20)
except BarangayServiceError as error:
    st.error(str(error))
    recent_updates = []

render_recent_updates_section(recent_updates)