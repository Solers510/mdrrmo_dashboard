from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from config.access_control import (
    PERMISSION_VALIDATE_BARANGAY_REPORTS,
)
from services.event_service import (
    EventDataIntegrityError,
    get_active_event_summary,
)
from services.validation_service import (
    ReportAlreadyReviewedError,
    ValidationAuthorizationError,
    ValidationDataIntegrityError,
    ValidationInputError,
    ValidationServiceError,
    get_barangay_validation_queue,
    get_evacuation_validation_queue,
    get_population_reconciliation_queue,
    review_barangay_update,
    review_evacuation_update,
)
from utils.auth import require_permission


current_user = require_permission(
    PERMISSION_VALIDATE_BARANGAY_REPORTS
)
MANILA_TIMEZONE = ZoneInfo("Asia/Manila")


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "Not available"
    return value.astimezone(MANILA_TIMEZONE).strftime(
        "%d %B %Y, %I:%M %p"
    )


def handle_review_error(error: Exception) -> None:
    if isinstance(error, ReportAlreadyReviewedError):
        st.warning(str(error))
    else:
        st.error(str(error))


def find_reconciliation(
    rows: list[dict[str, object]],
    barangay_name: str,
) -> dict[str, object] | None:
    return next(
        (
            row
            for row in rows
            if row["barangay_name"] == barangay_name
        ),
        None,
    )


st.title("Operational Report Validation")
st.caption(
    "Validate barangay and evacuation-center reports and reconcile "
    "differences before treating the data as official."
)

success_message = st.session_state.pop(
    "validation_success",
    None,
)
if success_message:
    st.success(success_message)

try:
    active_event = get_active_event_summary()
except EventDataIntegrityError as error:
    st.error(str(error))
    st.stop()
except Exception:
    st.error(
        "The active disaster event could not be loaded."
    )
    st.stop()

if active_event is None:
    st.warning("No active disaster event exists.")
    st.stop()

event_columns = st.columns(3)
event_columns[0].metric(
    "Active Event",
    str(active_event["event_name"]),
)
event_columns[1].metric(
    "Alert Level",
    str(active_event["alert_code"]),
)
event_columns[2].metric(
    "EOC Status",
    str(active_event["eoc_status"]),
)

try:
    barangay_queue = get_barangay_validation_queue()
    evacuation_queue = get_evacuation_validation_queue()
    reconciliation_rows = get_population_reconciliation_queue()
except ValidationServiceError as error:
    st.error(str(error))
    st.stop()
except Exception:
    st.error(
        "Operational validation data could not be loaded."
    )
    st.stop()

st.divider()

summary = st.columns(4)
summary[0].metric(
    "Barangay Reports Pending",
    len(barangay_queue),
)
summary[1].metric(
    "EC Reports Pending",
    len(evacuation_queue),
)
summary[2].metric(
    "Population Mismatches",
    sum(
        1
        for row in reconciliation_rows
        if row["reconciliation_status"]
        in {"Mismatch", "Allocation Conflict"}
    ),
)
summary[3].metric(
    "Missing Source Reports",
    sum(
        1
        for row in reconciliation_rows
        if row["reconciliation_status"]
        in {"No Barangay Report", "No EC Report"}
    ),
)

barangay_tab, ec_tab, reconciliation_tab = st.tabs(
    (
        "Barangay Reports",
        "Evacuation-Center Reports",
        "Population Reconciliation",
    )
)

with barangay_tab:
    st.subheader("Barangay Reports Awaiting Review")

    if not barangay_queue:
        st.success(
            "No barangay reports are waiting for validation."
        )
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": row["id"],
                        "Barangay": row["barangay_name"],
                        "Situation": row["situation_status"],
                        "Affected Families": row["affected_families"],
                        "Affected Individuals": row["affected_individuals"],
                        "Inside EC Families": row["inside_ec_families"],
                        "Inside EC Individuals": row["inside_ec_individuals"],
                        "Outside EC Families": row["outside_ec_families"],
                        "Outside EC Individuals": row["outside_ec_individuals"],
                        "Status": row["validation_status"],
                        "Source": row["source"],
                        "Recorded At": row["recorded_at"],
                    }
                    for row in barangay_queue
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        row_by_id = {
            int(row["id"]): row
            for row in barangay_queue
        }
        selected_id = st.selectbox(
            "Select barangay report",
            options=list(row_by_id),
            format_func=lambda report_id: (
                f"#{report_id} — "
                f"{row_by_id[report_id]['barangay_name']} — "
                f"{format_datetime(row_by_id[report_id]['recorded_at'])}"
            ),
            key="barangay_validation_select",
        )
        selected = row_by_id[selected_id]

        st.markdown(
            f"### Report #{selected_id}: "
            f"{selected['barangay_name']}"
        )

        pop = st.columns(4)
        pop[0].metric(
            "Affected Families",
            int(selected["affected_families"]),
        )
        pop[1].metric(
            "Affected Individuals",
            int(selected["affected_individuals"]),
        )
        pop[2].metric(
            "Inside EC Individuals",
            int(selected["inside_ec_individuals"]),
        )
        pop[3].metric(
            "Outside EC Individuals",
            int(selected["outside_ec_individuals"]),
        )

        reconciliation = find_reconciliation(
            reconciliation_rows,
            str(selected["barangay_name"]),
        )
        if reconciliation is not None:
            state = reconciliation["reconciliation_status"]
            if state == "Match":
                st.success(
                    "Barangay Inside-EC figures match the latest EC records."
                )
            elif state == "Allocation Conflict":
                st.error(
                    "Cross-barangay allocations currently exceed the "
                    "latest evacuation-center occupancy. Correct the "
                    "allocation or center occupancy before validation."
                )
            elif state == "Mismatch":
                st.warning(
                    "Inside-EC figures differ from the latest EC records: "
                    f"barangay {reconciliation['barangay_inside_families']} "
                    f"families / {reconciliation['barangay_inside_individuals']} "
                    "individuals versus EC records "
                    f"{reconciliation['ec_inside_families']} families / "
                    f"{reconciliation['ec_inside_individuals']} individuals. "
                    "Compare timestamps and source documents before validation."
                )
            elif state == "No EC Report":
                st.warning(
                    "The barangay reports people inside evacuation centers, "
                    "but no current EC report is available for comparison."
                )

        conditions = st.columns(4)
        conditions[0].write(
            f"**Flood:** {selected['flood_status']} "
            f"({selected['flood_depth_cm']} cm)"
        )
        conditions[1].write(
            f"**Road:** {selected['road_status']}"
        )
        conditions[2].write(
            f"**Power:** {selected['power_status']}"
        )
        conditions[3].write(
            f"**Water:** {selected['water_status']}"
        )

        st.write("**Source:**", selected["source"])
        st.write(
            "**Recorded at:**",
            format_datetime(selected["recorded_at"]),
        )
        st.write(
            "**Remarks:**",
            selected["remarks"] or "No remarks provided.",
        )

        with st.form(
            f"barangay_review_form_{selected_id}",
            clear_on_submit=False,
        ):
            decision = st.radio(
                "Decision *",
                options=("Validated", "Needs Correction"),
                horizontal=True,
                key=f"barangay_decision_{selected_id}",
            )
            st.info(
                f"Reviewer: {current_user.display_name} "
                f"— {current_user.role}"
            )
            notes = st.text_area(
                "Review notes",
                placeholder=(
                    "Record verification performed, supporting references, "
                    "or exact correction instructions."
                ),
                height=130,
                key=f"barangay_review_notes_{selected_id}",
            )
            confirm = st.checkbox(
                "I reviewed the figures, source, timing, and "
                "reconciliation information.",
                key=f"barangay_review_confirm_{selected_id}",
            )
            submitted = st.form_submit_button(
                "Save Barangay Review",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not confirm:
                st.error(
                    "Confirm that the report was reviewed before saving."
                )
            else:
                try:
                    review_barangay_update(
                        update_id=int(selected_id),
                        decision=decision,
                        reviewer_user_id=current_user.id,
                        review_notes=notes,
                    )
                except (
                    ValidationInputError,
                    ReportAlreadyReviewedError,
                    ValidationDataIntegrityError,
                    ValidationAuthorizationError,
                    ValidationServiceError,
                ) as error:
                    handle_review_error(error)
                except Exception:
                    st.error(
                        "The review could not be saved. "
                        "No review decision was recorded."
                    )
                else:
                    st.session_state["validation_success"] = (
                        f"Barangay report #{selected_id} "
                        f"was marked {decision}."
                    )
                    st.rerun()

with ec_tab:
    st.subheader(
        "Evacuation-Center Reports Awaiting Review"
    )

    if not evacuation_queue:
        st.success(
            "No evacuation-center reports are waiting for validation."
        )
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": row["id"],
                        "Center": row["center_name"],
                        "Barangay": row["barangay_name"],
                        "Center Status": row["status"],
                        "Families": row["families"],
                        "Individuals": row["individuals"],
                        "Food": row["food_status"],
                        "Water": row["water_status"],
                        "Electricity": row["electricity_status"],
                        "Validation": row["validation_status"],
                        "Source": row["source"],
                        "Recorded At": row["recorded_at"],
                    }
                    for row in evacuation_queue
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        ec_by_id = {
            int(row["id"]): row
            for row in evacuation_queue
        }
        selected_ec_id = st.selectbox(
            "Select evacuation-center report",
            options=list(ec_by_id),
            format_func=lambda report_id: (
                f"#{report_id} — "
                f"{ec_by_id[report_id]['center_name']} — "
                f"{format_datetime(ec_by_id[report_id]['recorded_at'])}"
            ),
            key="ec_validation_select",
        )
        selected_ec = ec_by_id[selected_ec_id]

        st.markdown(
            f"### Report #{selected_ec_id}: "
            f"{selected_ec['center_name']}"
        )

        metrics = st.columns(4)
        metrics[0].metric(
            "Families",
            int(selected_ec["families"]),
        )
        metrics[1].metric(
            "Individuals",
            int(selected_ec["individuals"]),
        )
        metrics[2].metric(
            "Safe Capacity",
            int(selected_ec["safe_capacity"]),
        )
        metrics[3].metric(
            "Center Status",
            str(selected_ec["status"]),
        )

        vulnerable = st.columns(5)
        vulnerable[0].metric(
            "Children",
            int(selected_ec["children"]),
        )
        vulnerable[1].metric(
            "Senior Citizens",
            int(selected_ec["senior_citizens"]),
        )
        vulnerable[2].metric(
            "PWD",
            int(selected_ec["pwd"]),
        )
        vulnerable[3].metric(
            "Pregnant Women",
            int(selected_ec["pregnant_women"]),
        )
        vulnerable[4].metric(
            "Medical Cases",
            int(selected_ec["medical_cases"]),
        )

        services = st.columns(4)
        services[0].write(
            f"**Food:** {selected_ec['food_status']}"
        )
        services[1].write(
            f"**Water:** {selected_ec['water_status']}"
        )
        services[2].write(
            f"**Electricity:** {selected_ec['electricity_status']}"
        )
        services[3].write(
            f"**Sanitation:** {selected_ec['sanitation_status']}"
        )

        reconciliation = find_reconciliation(
            reconciliation_rows,
            str(selected_ec["barangay_name"]),
        )
        if reconciliation is not None:
            state = reconciliation["reconciliation_status"]
            if state == "Allocation Conflict":
                st.error(
                    "Cross-barangay allocations currently exceed the "
                    "latest center occupancy. Reconcile this exception "
                    "before validating the report."
                )
            elif state == "Mismatch":
                st.warning(
                    "The latest barangay Inside-EC count differs from "
                    "the latest combined EC records for this barangay. "
                    "Compare report times before validating."
                )
            elif state == "No Barangay Report":
                st.warning(
                    "No current barangay report is available for "
                    "population or cross-barangay reconciliation."
                )
            elif state == "Match":
                st.success(
                    "Latest barangay and EC Inside-EC totals match."
                )

        st.write("**Source:**", selected_ec["source"])
        st.write(
            "**Recorded at:**",
            format_datetime(selected_ec["recorded_at"]),
        )
        st.write(
            "**Remarks:**",
            selected_ec["remarks"] or "No remarks provided.",
        )

        with st.form(
            f"ec_review_form_{selected_ec_id}",
            clear_on_submit=False,
        ):
            ec_decision = st.radio(
                "Decision *",
                options=("Validated", "Needs Correction"),
                horizontal=True,
                key=f"ec_decision_{selected_ec_id}",
            )
            st.info(
                f"Reviewer: {current_user.display_name} "
                f"— {current_user.role}"
            )
            ec_notes = st.text_area(
                "Review notes",
                placeholder=(
                    "Record verification performed, supporting references, "
                    "or exact correction instructions."
                ),
                height=130,
                key=f"ec_review_notes_{selected_ec_id}",
            )
            ec_confirm = st.checkbox(
                "I reviewed occupancy, vulnerable groups, services, "
                "source, timing, and reconciliation information.",
                key=f"ec_review_confirm_{selected_ec_id}",
            )
            ec_submitted = st.form_submit_button(
                "Save Evacuation-Center Review",
                type="primary",
                use_container_width=True,
            )

        if ec_submitted:
            if not ec_confirm:
                st.error(
                    "Confirm that the report was reviewed before saving."
                )
            else:
                try:
                    review_evacuation_update(
                        update_id=int(selected_ec_id),
                        decision=ec_decision,
                        reviewer_user_id=current_user.id,
                        review_notes=ec_notes,
                    )
                except (
                    ValidationInputError,
                    ReportAlreadyReviewedError,
                    ValidationDataIntegrityError,
                    ValidationAuthorizationError,
                    ValidationServiceError,
                ) as error:
                    handle_review_error(error)
                except Exception:
                    st.error(
                        "The review could not be saved. "
                        "No review decision was recorded."
                    )
                else:
                    st.session_state["validation_success"] = (
                        f"Evacuation-center report #{selected_ec_id} "
                        f"was marked {ec_decision}."
                    )
                    st.rerun()

with reconciliation_tab:
    st.subheader(
        "Barangay / Evacuation-Center Reconciliation"
    )
    st.caption(
        "A mismatch does not automatically mean one report is wrong. "
        "Compare timestamps and source documents because reports may "
        "arrive at different times."
    )

    if not reconciliation_rows:
        st.info(
            "No reconciliation data is available."
        )
    else:
        table = pd.DataFrame(
            [
                {
                    "Barangay": row["barangay_name"],
                    "Barangay Inside EC — Families": (
                        row["barangay_inside_families"]
                    ),
                    "EC Records — Families": (
                        row["ec_inside_families"]
                    ),
                    "Family Difference": (
                        row["family_difference"]
                    ),
                    "Barangay Inside EC — Individuals": (
                        row["barangay_inside_individuals"]
                    ),
                    "EC Records — Individuals": (
                        row["ec_inside_individuals"]
                    ),
                    "Individual Difference": (
                        row["individual_difference"]
                    ),
                    "Operational ECs": (
                        row["ec_operational_centers"]
                    ),
                    "Status": (
                        row["reconciliation_status"]
                    ),
                    "Barangay Report Time": (
                        row["barangay_recorded_at"]
                    ),
                    "Latest EC Report Time": (
                        row["latest_ec_recorded_at"]
                    ),
                }
                for row in reconciliation_rows
            ]
        )
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
        )

        mismatches = [
            row
            for row in reconciliation_rows
            if row["reconciliation_status"]
            in {"Mismatch", "Allocation Conflict"}
        ]
        if mismatches:
            st.warning(
                f"{len(mismatches)} barangay(s) require "
                "population reconciliation."
            )
        else:
            st.success(
                "No current barangay/EC population mismatches were detected."
            )
