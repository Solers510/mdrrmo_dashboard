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
from utils.ui import (
    render_attention_required,
    render_dashboard_section_header,
    render_kpi_grid,
    render_operational_event_strip,
    render_operational_page_header,
)


current_user = require_permission(
    PERMISSION_VALIDATE_BARANGAY_REPORTS
)
MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

RECONCILIATION_ACTION_STATUSES = frozenset(
    {
        "Mismatch",
        "Allocation Conflict",
        "No Barangay Report",
        "No EC Report",
    }
)


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "Not available"
    return value.astimezone(MANILA_TIMEZONE).strftime(
        "%d %B %Y, %I:%M %p"
    )


def format_report_age(value: datetime | None) -> str:
    if value is None:
        return "No report"

    localized = value.astimezone(MANILA_TIMEZONE)
    now = datetime.now(MANILA_TIMEZONE)
    seconds = max(int((now - localized).total_seconds()), 0)

    if seconds < 60:
        return "<1m"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"

    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"

    return f"{hours // 24}d"


def display_event_name(event: dict[str, object]) -> str:
    classification = event.get("classification")
    event_name = str(event["event_name"])

    if classification is not None and str(classification).strip():
        return f"{classification} {event_name}"

    return event_name


def display_sitrep(event: dict[str, object]) -> str:
    value = event.get("current_sitrep_number")
    return "Not set" if value in {None, ""} else str(value)


def format_pair(left: object, right: object) -> str:
    left_text = "—" if left is None else f"{int(left):,}"
    right_text = "—" if right is None else f"{int(right):,}"
    return f"{left_text} / {right_text}"


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


render_operational_page_header(
    title="Report Validation",
    subtitle=(
        "Review submitted barangay and evacuation-center reports, compare "
        "source timing and reconciliation signals, and record a formal decision."
    ),
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

render_operational_event_strip(
    event_name=display_event_name(active_event),
    hazard_type=str(active_event["hazard_type"]),
    alert_code=str(active_event["alert_code"]),
    eoc_status=str(active_event["eoc_status"]),
    sitrep=display_sitrep(active_event),
    official_reference=(
        str(active_event["official_reference"])
        if active_event.get("official_reference")
        else None
    ),
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

population_exceptions = sum(
    1
    for row in reconciliation_rows
    if row["reconciliation_status"]
    in {"Mismatch", "Allocation Conflict"}
)
missing_source_reports = sum(
    1
    for row in reconciliation_rows
    if row["reconciliation_status"]
    in {"No Barangay Report", "No EC Report"}
)
reconciliation_action_count = sum(
    1
    for row in reconciliation_rows
    if row["reconciliation_status"]
    in RECONCILIATION_ACTION_STATUSES
)
allocation_conflicts = sum(
    1
    for row in reconciliation_rows
    if row["reconciliation_status"] == "Allocation Conflict"
)

render_dashboard_section_header(
    title="Validation Workload",
    subtitle=(
        "Current submitted reports and reconciliation exceptions requiring "
        "validator attention."
    ),
)

attention_items = []

if barangay_queue:
    attention_items.append(
        {
            "label": "Barangay Reviews",
            "value": len(barangay_queue),
            "tone": "info",
        }
    )

if evacuation_queue:
    attention_items.append(
        {
            "label": "EC Reviews",
            "value": len(evacuation_queue),
            "tone": "info",
        }
    )

if population_exceptions:
    attention_items.append(
        {
            "label": "Population Exceptions",
            "value": population_exceptions,
            "tone": "danger" if allocation_conflicts else "warning",
        }
    )

if missing_source_reports:
    attention_items.append(
        {
            "label": "Missing Source Reports",
            "value": missing_source_reports,
            "tone": "warning",
        }
    )

render_attention_required(attention_items)

barangay_tab, ec_tab, reconciliation_tab = st.tabs(
    (
        f"Barangay Queue ({len(barangay_queue)})",
        f"EC Queue ({len(evacuation_queue)})",
        f"Reconciliation ({reconciliation_action_count})",
    )
)

with barangay_tab:
    render_dashboard_section_header(
        title="Barangay Validation Queue",
        subtitle=(
            "Review submitted barangay reports in queue order. Select one report "
            "to inspect source, timing, operating conditions, and reconciliation."
        ),
    )

    if not barangay_queue:
        st.success(
            "No barangay reports are waiting for validation."
        )
    else:
        barangay_queue_rows = [
            {
                "Report": int(row["id"]),
                "Barangay": row["barangay_name"],
                "Situation": row["situation_status"],
                "Affected F / I": (
                    f"{int(row['affected_families']):,} / "
                    f"{int(row['affected_individuals']):,}"
                ),
                "Displaced": (
                    int(row["inside_ec_individuals"])
                    + int(row["outside_ec_individuals"])
                ),
                "Age": format_report_age(row["recorded_at"]),
            }
            for row in barangay_queue
        ]

        st.dataframe(
            pd.DataFrame(barangay_queue_rows),
            width="stretch",
            hide_index=True,
            column_config={
                "Report": st.column_config.NumberColumn(
                    "#",
                    width=55,
                    format="%d",
                ),
                "Barangay": st.column_config.TextColumn(
                    "Barangay",
                    width=165,
                    pinned=True,
                ),
                "Situation": st.column_config.TextColumn(
                    "Situation",
                    width=100,
                ),
                "Affected F / I": st.column_config.TextColumn(
                    "Affected F / I",
                    help="Affected families / affected individuals",
                    width=110,
                ),
                "Displaced": st.column_config.NumberColumn(
                    "Displaced",
                    width=85,
                    format="%d",
                ),
                "Age": st.column_config.TextColumn(
                    "Age",
                    width=55,
                ),
            },
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

        render_dashboard_section_header(
            title=f"Review Report #{selected_id} — {selected['barangay_name']}",
            subtitle=(
                f"Recorded {format_datetime(selected['recorded_at'])}. "
                "Review the operational figures and source context before deciding."
            ),
        )

        render_kpi_grid(
            [
                {
                    "label": "Affected Families",
                    "value": f"{int(selected['affected_families']):,}",
                },
                {
                    "label": "Affected Individuals",
                    "value": f"{int(selected['affected_individuals']):,}",
                },
                {
                    "label": "Inside EC Individuals",
                    "value": f"{int(selected['inside_ec_individuals']):,}",
                },
                {
                    "label": "Outside EC Individuals",
                    "value": f"{int(selected['outside_ec_individuals']):,}",
                },
            ],
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
                width="stretch",
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
    render_dashboard_section_header(
        title="Evacuation-Center Validation Queue",
        subtitle=(
            "Review submitted center reports with occupancy, service condition, "
            "source timing, vulnerable groups, and reconciliation context."
        ),
    )

    if not evacuation_queue:
        st.success(
            "No evacuation-center reports are waiting for validation."
        )
    else:
        ec_queue_rows = [
            {
                "Report": int(row["id"]),
                "Center": row["center_name"],
                "Status": row["status"],
                "Occupancy F / I": (
                    f"{int(row['families']):,} / "
                    f"{int(row['individuals']):,}"
                ),
                "Food · Water · Power": (
                    f"{row['food_status']} · "
                    f"{row['water_status']} · "
                    f"{row['electricity_status']}"
                ),
                "Age": format_report_age(row["recorded_at"]),
            }
            for row in evacuation_queue
        ]

        st.dataframe(
            pd.DataFrame(ec_queue_rows),
            width="stretch",
            hide_index=True,
            column_config={
                "Report": st.column_config.NumberColumn(
                    "#",
                    width=55,
                    format="%d",
                ),
                "Center": st.column_config.TextColumn(
                    "Center",
                    width=225,
                    pinned=True,
                ),
                "Status": st.column_config.TextColumn(
                    "Status",
                    width=75,
                ),
                "Occupancy F / I": st.column_config.TextColumn(
                    "Occupancy F / I",
                    help="Registered families / registered individuals",
                    width=110,
                ),
                "Food · Water · Power": st.column_config.TextColumn(
                    "Food · Water · Power",
                    width=215,
                ),
                "Age": st.column_config.TextColumn(
                    "Age",
                    width=55,
                ),
            },
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

        render_dashboard_section_header(
            title=f"Review Report #{selected_ec_id} — {selected_ec['center_name']}",
            subtitle=(
                f"Host barangay: {selected_ec['barangay_name']} · "
                f"Recorded {format_datetime(selected_ec['recorded_at'])}."
            ),
        )

        render_kpi_grid(
            [
                {
                    "label": "Families",
                    "value": f"{int(selected_ec['families']):,}",
                },
                {
                    "label": "Individuals",
                    "value": f"{int(selected_ec['individuals']):,}",
                },
                {
                    "label": "Safe Capacity",
                    "value": f"{int(selected_ec['safe_capacity']):,}",
                },
                {
                    "label": "Center Status",
                    "value": str(selected_ec["status"]),
                },
            ],
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
                width="stretch",
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
    render_dashboard_section_header(
        title="Source Reconciliation",
        subtitle=(
            "Compare barangay Inside-EC figures with evacuation-center records. "
            "Differences are review signals, not automatic proof that a source is wrong."
        ),
    )

    if not reconciliation_rows:
        st.info("No reconciliation data is available.")
    else:
        matches = sum(
            1
            for row in reconciliation_rows
            if row["reconciliation_status"] == "Match"
        )
        mismatches = sum(
            1
            for row in reconciliation_rows
            if row["reconciliation_status"] == "Mismatch"
        )
        missing_sources = sum(
            1
            for row in reconciliation_rows
            if row["reconciliation_status"]
            in {"No Barangay Report", "No EC Report"}
        )
        allocation_conflicts = sum(
            1
            for row in reconciliation_rows
            if row["reconciliation_status"] == "Allocation Conflict"
        )

        render_kpi_grid(
            [
                {"label": "Matches", "value": matches},
                {"label": "Mismatches", "value": mismatches},
                {"label": "Missing Source", "value": missing_sources},
                {
                    "label": "Allocation Conflicts",
                    "value": allocation_conflicts,
                },
            ],
        )

        problem_rows = [
            row
            for row in reconciliation_rows
            if row["reconciliation_status"]
            in RECONCILIATION_ACTION_STATUSES
        ]
        no_current_data_count = sum(
            1
            for row in reconciliation_rows
            if row["reconciliation_status"] == "No Current Data"
        )

        if problem_rows:
            st.warning(
                f"{len(problem_rows)} barangay(s) currently require source "
                "or population reconciliation."
            )

            routine_rows = [
                {
                    "Barangay": row["barangay_name"],
                    "Status": row["reconciliation_status"],
                    "Families B / EC": format_pair(
                        row["barangay_inside_families"],
                        row["ec_inside_families"],
                    ),
                    "Individuals B / EC": format_pair(
                        row["barangay_inside_individuals"],
                        row["ec_inside_individuals"],
                    ),
                    "Barangay Age": format_report_age(
                        row["barangay_recorded_at"]
                    ),
                    "EC Source Age": format_report_age(
                        row["latest_ec_recorded_at"]
                    ),
                }
                for row in problem_rows
            ]

            st.dataframe(
                pd.DataFrame(routine_rows),
                width="stretch",
                hide_index=True,
                column_config={
                    "Barangay": st.column_config.TextColumn(
                        "Barangay",
                        width=165,
                        pinned=True,
                    ),
                    "Status": st.column_config.TextColumn(
                        "Status",
                        width=150,
                    ),
                    "Families B / EC": st.column_config.TextColumn(
                        "Families B / EC",
                        help="Barangay Inside-EC families / EC-record families",
                        width=120,
                    ),
                    "Individuals B / EC": st.column_config.TextColumn(
                        "Individuals B / EC",
                        help=(
                            "Barangay Inside-EC individuals / "
                            "EC-record individuals"
                        ),
                        width=130,
                    ),
                    "Barangay Age": st.column_config.TextColumn(
                        "Barangay Age",
                        width=95,
                    ),
                    "EC Source Age": st.column_config.TextColumn(
                        "EC Source Age",
                        width=95,
                    ),
                },
            )
        else:
            st.success(
                "No current barangay/EC source or population reconciliation "
                "issue requires validator action."
            )

        if no_current_data_count:
            st.caption(
                f"{no_current_data_count} barangay(s) have no current report "
                "from either comparison source. They are excluded from the "
                "action queue and remain available in the full source view below."
            )

        with st.expander(
            "Full reconciliation source timestamps",
            expanded=False,
        ):
            full_rows = [
                {
                    "Barangay": row["barangay_name"],
                    "Barangay Inside EC — Families": row["barangay_inside_families"],
                    "EC Records — Families": row["ec_inside_families"],
                    "Family Difference": row["family_difference"],
                    "Barangay Inside EC — Individuals": (
                        row["barangay_inside_individuals"]
                    ),
                    "EC Records — Individuals": row["ec_inside_individuals"],
                    "Individual Difference": row["individual_difference"],
                    "Operational ECs": row["ec_operational_centers"],
                    "Status": row["reconciliation_status"],
                    "Barangay Report Time": row["barangay_recorded_at"],
                    "Latest EC Report Time": row["latest_ec_recorded_at"],
                }
                for row in reconciliation_rows
            ]

            st.dataframe(
                pd.DataFrame(full_rows),
                width="stretch",
                hide_index=True,
            )

        st.caption(
            "Before validating or correcting figures, compare source documents "
            "and timestamps. Reconciliation remains a warning workflow and does "
            "not rewrite operational reports."
        )
