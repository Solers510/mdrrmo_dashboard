from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from utils.error_handling import log_exception

from config.constants import (
    ELECTRICITY_STATUSES,
    EVACUATION_CENTER_STATUSES,
    SUPPLY_STATUSES,
)
from services.barangay_service import (
    BarangayServiceError,
    list_active_barangays,
)
from services.event_service import (
    EventDataIntegrityError,
    get_active_event_summary,
)
from services.cross_barangay_service import (
    CrossBarangayAuthorizationError,
    CrossBarangayDataIntegrityError,
    CrossBarangayServiceError,
    CrossBarangayValidationError,
    DuplicateCrossBarangaySubmissionError,
    create_cross_barangay_allocation,
    get_cross_barangay_context,
    list_current_cross_barangay_allocations,
)
from services.evacuation_service import (
    EvacuationDataIntegrityError,
    EvacuationServiceError,
    EvacuationValidationError,
    NoActiveEventError,
    create_evacuation_center,
    create_evacuation_center_update,
    get_pending_evacuation_correction,
    get_recent_evacuation_updates,
    list_active_evacuation_centers,
)
from config.access_control import (
    PERMISSION_MANAGE_EVACUATION_CENTERS,
    PERMISSION_SUBMIT_EVACUATION_UPDATES,
)
from utils.auth import has_permission, require_any_permission
from utils.ui import (
    render_dashboard_section_header,
    render_kpi_grid,
    render_operational_event_strip,
    render_operational_page_header,
    render_workflow_section,
)


current_user = require_any_permission(
    PERMISSION_MANAGE_EVACUATION_CENTERS,
    PERMISSION_SUBMIT_EVACUATION_UPDATES,
)


can_manage_centers = has_permission(
    current_user,
    PERMISSION_MANAGE_EVACUATION_CENTERS,
)


def select_index(
    options,
    value: object,
    fallback: int = 0,
) -> int:
    try:
        return list(options).index(str(value))
    except ValueError:
        return fallback


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")


def format_report_age(value: datetime | None) -> str:
    if value is None:
        return "—"

    now = datetime.now(MANILA_TIMEZONE)
    localized = value.astimezone(MANILA_TIMEZONE)
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
    name = str(event["event_name"])
    if classification is not None and str(classification).strip():
        return f"{classification} {name}"
    return name


def display_sitrep(event: dict[str, object]) -> str:
    value = event.get("current_sitrep_number")
    return "Not set" if value in {None, ""} else str(value)


render_operational_page_header(
    title="Evacuation Center Monitoring",
    subtitle=(
        "Record occupancy, vulnerable populations, essential services, "
        "cross-barangay allocations, and source information."
    ),
)


success_message = st.session_state.pop(
    "evacuation_success",
    None,
)

if success_message:
    st.success(success_message)


try:
    active_event = get_active_event_summary()

except EventDataIntegrityError as error:
    st.error(str(error))
    st.stop()

except Exception as error:
    st.error(
        "The active disaster event could not be loaded."
    )
    st.caption(f"Error reference: {log_exception("Evacuation Centers", error)}")
    st.stop()


if active_event is None:
    st.warning(
        "No active disaster event exists. Create one "
        "through Event Control first."
    )
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
    barangays = list_active_barangays()
    centers = list_active_evacuation_centers()

except (
    BarangayServiceError,
    EvacuationServiceError,
) as error:
    st.error(str(error))
    st.stop()


barangay_label_to_id = {
    f"{record['name']} — {record['psgc_code']}": int(
        record["id"]
    )
    for record in barangays
}

barangay_labels = list(barangay_label_to_id.keys())


update_tab, manage_tab, cross_tab, history_tab = st.tabs(
    (
        "Occupancy Update",
        f"Center Registry ({len(centers)})",
        "Cross-Barangay",
        "Recent Reports",
    )
)


# ---------------------------------------------------------
# MANAGE CENTERS
# ---------------------------------------------------------

with manage_tab:
    render_dashboard_section_header(
        title="Evacuation Center Registry",
        subtitle=(
            "Create and review official center master records. Only authorized "
            "operations staff may add centers."
        ),
    )

    st.markdown("**Add official evacuation center**")

    if not can_manage_centers:
        st.warning(
            "Your role may submit evacuation-center "
            "updates, but only authorized operations "
            "staff can create evacuation-center "
            "master records."
        )

    st.info(
        "Use only official evacuation-center names and "
        "capacity values supplied by the responsible office."
    )

    with st.form("create_evacuation_center_form"):
        center_name = st.text_input(
            "Official center name *",
            placeholder=(
                "Example: Naic Elementary School"
            ),
        )

        selected_barangay_label = st.selectbox(
            "Barangay *",
            options=barangay_labels,
        )

        address = st.text_input(
            "Address or location description"
        )

        safe_capacity = st.number_input(
            "Safe capacity *",
            min_value=0,
            step=1,
            help=(
                "Confirm whether the office measures this "
                "in individuals or families before using "
                "occupancy percentages."
            ),
        )

        confirmation = st.checkbox(
            "I verified this center against an official "
            "evacuation-center list."
        )

        create_submitted = st.form_submit_button(
            "Add Evacuation Center",
            type="primary",
            width="stretch",
            disabled=not can_manage_centers,
        )

    if create_submitted:
        if not can_manage_centers:
            st.error(
                "You do not have permission to create "
                "evacuation-center master records."
            )

        elif not confirmation:
            st.error(
                "Confirm the official center information "
                "before saving."
            )

        else:
            selected_barangay_id = (
                barangay_label_to_id[
                    selected_barangay_label
                ]
            )

            try:
                center_id = create_evacuation_center(
                    name=center_name,
                    barangay_id=selected_barangay_id,
                    address=address,
                    safe_capacity=int(safe_capacity),
                    actor_user_id=current_user.id,
                )

            except EvacuationValidationError as error:
                st.error(str(error))

            except EvacuationServiceError as error:
                st.error(str(error))

            except Exception as error:
                st.error(
                    "An unexpected database error occurred."
                )
                st.caption(f"Error reference: {log_exception("Evacuation Centers", error)}")
            else:
                st.session_state[
                    "evacuation_success"
                ] = (
                    f"Evacuation center #{center_id} "
                    "was created successfully."
                )

                st.rerun()

    render_dashboard_section_header(
        title="Active Evacuation Centers",
        subtitle=(
            "Current official center records available for operational reporting."
        ),
    )

    if not centers:
        st.info(
            "No active evacuation centers have been added."
        )

    else:
        center_table = pd.DataFrame(
            [
                {
                    "ID": center["id"],
                    "Center": center["name"],
                    "Barangay": center["barangay_name"],
                    "Address": center["address"] or "—",
                    "Safe Capacity": (
                        center["safe_capacity"]
                    ),
                }
                for center in centers
            ]
        )

        st.dataframe(
            center_table,
            width="stretch",
            hide_index=True,
        )


# ---------------------------------------------------------
# OCCUPANCY UPDATE
# ---------------------------------------------------------

with update_tab:
    render_dashboard_section_header(
        title="Record Evacuation-Center Report",
        subtitle=(
            f"Submitting as {current_user.display_name} — {current_user.role}. "
            "Required fields are marked with an asterisk."
        ),
    )

    if not centers:
        st.warning(
            "Create at least one evacuation-center master "
            "record before recording an update."
        )

    else:
        render_workflow_section(
            step=1,
            title="Select Evacuation Center",
            subtitle=(
                "Choose the center being reported. Correction-required reports "
                "for the selected center load automatically."
            ),
        )

        center_label_to_id = {
            (
                f"{center['name']} — "
                f"{center['barangay_name']}"
            ): int(center["id"])
            for center in centers
        }

        center_labels = list(
            center_label_to_id.keys()
        )

        evacuation_update_form_nonce = int(
            st.session_state.setdefault(
                "evacuation_update_form_nonce",
                0,
            )
        )

        evacuation_submission_state_key = (
            f"evacuation_submission_key_{evacuation_update_form_nonce}"
        )

        if evacuation_submission_state_key not in st.session_state:
            st.session_state[evacuation_submission_state_key] = str(uuid4())

        selected_center_label = st.selectbox(
            "Evacuation center *",
            options=center_labels,
            key=(
                f"evacuation_center_selector_"
                f"{evacuation_update_form_nonce}"
            ),
        )

        selected_center_id = (
            center_label_to_id[
                selected_center_label
            ]
        )

        selected_center = next(
            center
            for center in centers
            if int(center["id"]) == int(selected_center_id)
        )

        render_kpi_grid(
            [
                {
                    "label": "Host Barangay",
                    "value": str(selected_center["barangay_name"]),
                },
                {
                    "label": "Safe Capacity",
                    "value": f"{int(selected_center['safe_capacity'] or 0):,}",
                },
                {
                    "label": "Registry ID",
                    "value": f"#{int(selected_center['id'])}",
                },
            ],
            compact=True,
        )

        try:
            pending_correction = (
                get_pending_evacuation_correction(
                    center_id=selected_center_id
                )
            )
        except EvacuationServiceError as error:
            st.error(str(error))
            pending_correction = None

        correction_id = (
            int(pending_correction["id"])
            if pending_correction is not None
            else None
        )

        if pending_correction is not None:
            st.error(
                f"Correction Required — Evacuation-Center "
                f"Report #{correction_id}"
            )

            correction_columns = st.columns(2)

            with correction_columns[0]:
                st.write(
                    "**Reviewed by:** "
                    + str(
                        pending_correction["reviewed_by"]
                        or "Authorized validator"
                    )
                )

            with correction_columns[1]:
                st.write(
                    "**Reviewed at:** "
                    + str(
                        pending_correction["reviewed_at"]
                        or "Not recorded"
                    )
                )

            st.warning(
                "**Validator instructions:** "
                + str(
                    pending_correction["review_notes"]
                    or "No correction instructions were recorded."
                )
            )

            st.info(
                f"The form below is prefilled from Report "
                f"#{correction_id}. Submitting the corrected "
                f"report will supersede Report #{correction_id}; "
                f"the original remains in history."
            )

        correction_form_suffix = (
            f"correction_{correction_id}"
            if correction_id is not None
            else "new"
        )

        with st.form(
            (
                f"evacuation_update_form_"
                f"{evacuation_update_form_nonce}_"
                f"{selected_center_id}_"
                f"{correction_form_suffix}"
            ),
            clear_on_submit=False,
        ):
            render_workflow_section(
                step=2,
                title="Status & Occupancy",
                subtitle=(
                    "Record the center operating status and current registered "
                    "families and individuals."
                ),
            )

            status = st.selectbox(
                "Center status *",
                options=EVACUATION_CENTER_STATUSES,
                index=(
                    select_index(
                        EVACUATION_CENTER_STATUSES,
                        pending_correction["status"],
                    )
                    if pending_correction is not None
                    else 0
                ),
            )

            occupancy_columns = st.columns(2)

            with occupancy_columns[0]:
                families = st.number_input(
                    "Families",
                    min_value=0,
                    step=1,
                    value=(
                        int(pending_correction["families"])
                        if pending_correction is not None
                        else 0
                    ),
                )

            with occupancy_columns[1]:
                individuals = st.number_input(
                    "Individuals",
                    min_value=0,
                    step=1,
                    value=(
                        int(pending_correction["individuals"])
                        if pending_correction is not None
                        else 0
                    ),
                )

            render_workflow_section(
                step=3,
                title="Vulnerable Groups",
                subtitle=(
                    "Record vulnerable evacuees and current medical cases from "
                    "the latest verified center register."
                ),
            )

            vulnerable_row_1 = st.columns(3)

            with vulnerable_row_1[0]:
                children = st.number_input(
                    "Children",
                    min_value=0,
                    step=1,
                    value=(
                        int(pending_correction["children"])
                        if pending_correction is not None
                        else 0
                    ),
                )

            with vulnerable_row_1[1]:
                senior_citizens = st.number_input(
                    "Senior citizens",
                    min_value=0,
                    step=1,
                    value=(
                        int(pending_correction["senior_citizens"])
                        if pending_correction is not None
                        else 0
                    ),
                )

            with vulnerable_row_1[2]:
                pwd = st.number_input(
                    "Persons with disabilities",
                    min_value=0,
                    step=1,
                    value=(
                        int(pending_correction["pwd"])
                        if pending_correction is not None
                        else 0
                    ),
                )

            vulnerable_row_2 = st.columns(2)

            with vulnerable_row_2[0]:
                pregnant_women = st.number_input(
                    "Pregnant women",
                    min_value=0,
                    step=1,
                    value=(
                        int(pending_correction["pregnant_women"])
                        if pending_correction is not None
                        else 0
                    ),
                )

            with vulnerable_row_2[1]:
                medical_cases = st.number_input(
                    "Medical cases",
                    min_value=0,
                    step=1,
                    value=(
                        int(pending_correction["medical_cases"])
                        if pending_correction is not None
                        else 0
                    ),
                )

            render_workflow_section(
                step=4,
                title="Essential Services",
                subtitle=(
                    "Record food, water, electricity, and sanitation conditions."
                ),
            )

            service_columns = st.columns(3)

            with service_columns[0]:
                food_status = st.selectbox(
                    "Food status",
                    options=SUPPLY_STATUSES,
                    index=(
                        select_index(
                            SUPPLY_STATUSES,
                            pending_correction["food_status"],
                        )
                        if pending_correction is not None
                        else 0
                    ),
                )

            with service_columns[1]:
                water_status = st.selectbox(
                    "Water status",
                    options=SUPPLY_STATUSES,
                    index=(
                        select_index(
                            SUPPLY_STATUSES,
                            pending_correction["water_status"],
                        )
                        if pending_correction is not None
                        else 0
                    ),
                )

            with service_columns[2]:
                electricity_status = st.selectbox(
                    "Electricity status",
                    options=ELECTRICITY_STATUSES,
                    index=(
                        select_index(
                            ELECTRICITY_STATUSES,
                            pending_correction["electricity_status"],
                        )
                        if pending_correction is not None
                        else 0
                    ),
                )

            sanitation_status = st.text_input(
                "Sanitation status *",
                value=(
                    str(pending_correction["sanitation_status"])
                    if pending_correction is not None
                    else ""
                ),
                placeholder=(
                    "Use the wording from the official form."
                ),
            )

            render_workflow_section(
                step=5,
                title="Source & Submit",
                subtitle=(
                    "Identify the source, add useful context, review the report, "
                    "and submit it for validation."
                ),
            )

            source = st.text_input(
                "Information source *",
                value=(
                    str(pending_correction["source"])
                    if pending_correction is not None
                    else ""
                ),
                placeholder=(
                    "Camp manager, MSWDO, field team, "
                    "official center report"
                ),
            )

            remarks = st.text_area(
                "Remarks",
                value=(
                    str(pending_correction["remarks"] or "")
                    if pending_correction is not None
                    else ""
                ),
                height=120,
            )

            st.info(
                "The report will be saved as Submitted and will appear "
                "in Report Validation for review."
            )

            confirmation = st.checkbox(
                "I reviewed the occupancy figures and source."
            )

            update_submitted = st.form_submit_button(
                "Save Evacuation Update",
                type="primary",
                width="stretch",
            )

        if update_submitted:
            if not confirmation:
                st.error(
                    "Confirm the report before saving."
                )

            else:
                try:
                    update_id = (
                        create_evacuation_center_update(
                            center_id=selected_center_id,
                            status=status,
                            families=int(families),
                            individuals=int(individuals),
                            children=int(children),
                            senior_citizens=int(
                                senior_citizens
                            ),
                            pwd=int(pwd),
                            pregnant_women=int(
                                pregnant_women
                            ),
                            medical_cases=int(
                                medical_cases
                            ),
                            food_status=food_status,
                            water_status=water_status,
                            electricity_status=(
                                electricity_status
                            ),
                            sanitation_status=(
                                sanitation_status
                            ),
                            source=source,
                            remarks=remarks,
                            submission_key=st.session_state[
                                evacuation_submission_state_key
                            ],
                            submitter_user_id=current_user.id,
                        )
                    )

                except NoActiveEventError as error:
                    st.warning(str(error))

                except (
                    EvacuationValidationError,
                    EvacuationDataIntegrityError,
                    EvacuationServiceError,
                ) as error:
                    st.error(str(error))

                except Exception as error:
                    st.error(
                        "An unexpected database error "
                        "occurred."
                    )
                    st.caption(f"Error reference: {log_exception("Evacuation Centers", error)}")
                else:
                    st.session_state[
                        "evacuation_update_form_nonce"
                    ] = evacuation_update_form_nonce + 1

                    st.session_state.pop(
                        evacuation_submission_state_key,
                        None,
                    )

                    st.session_state[
                        "evacuation_success"
                    ] = (
                        f"Evacuation update #{update_id} "
                        "was saved successfully."
                    )

                    st.rerun()



# ---------------------------------------------------------
# CROSS-BARANGAY EXCEPTION
# ---------------------------------------------------------

with cross_tab:
    render_dashboard_section_header(
        title="Cross-Barangay Evacuation Allocation",
        subtitle=(
            "Use this exception workflow only when evacuees are staying in a "
            "center outside their home barangay."
        ),
    )

    if not can_manage_centers:
        st.warning(
            "Only an Operations Officer or Administrator may "
            "record this exception."
        )
    elif not centers:
        st.info("No active evacuation centers are available.")
    else:
        center_by_id = {
            int(center["id"]): center
            for center in centers
        }

        selected_cross_center_id = st.selectbox(
            "Host evacuation center *",
            options=list(center_by_id),
            format_func=lambda center_id: (
                f"{center_by_id[center_id]['name']} — "
                f"{center_by_id[center_id]['barangay_name']}"
            ),
            key="cross_barangay_center",
        )

        try:
            cross_context = get_cross_barangay_context(
                center_id=int(selected_cross_center_id)
            )
        except CrossBarangayServiceError as error:
            st.error(str(error))
            cross_context = None

        if cross_context is not None:
            latest_update = cross_context["latest_ec_update"]

            if latest_update is None:
                st.warning(
                    "This center has no current occupancy report. "
                    "Record the center occupancy first."
                )
            else:
                render_kpi_grid(
                    [
                        {
                            "label": "Latest EC Families",
                            "value": f"{int(latest_update['families']):,}",
                        },
                        {
                            "label": "Latest EC Individuals",
                            "value": f"{int(latest_update['individuals']):,}",
                        },
                        {
                            "label": "Center Status",
                            "value": str(latest_update["status"]),
                        },
                        {
                            "label": "Foreign Origins",
                            "value": (
                                f"{len(cross_context['current_allocations']):,}"
                            ),
                        },
                    ],
                    compact=True,
                )

                origin_options = [
                    record
                    for record in barangays
                    if int(record["id"])
                    != int(cross_context["host_barangay_id"])
                ]

                if not origin_options:
                    st.info(
                        "No other active barangays are available."
                    )
                else:
                    origin_by_id = {
                        int(record["id"]): record
                        for record in origin_options
                    }

                    nonce = int(
                        st.session_state.setdefault(
                            "cross_allocation_nonce",
                            0,
                        )
                    )
                    token_key = (
                        f"cross_allocation_token_{nonce}"
                    )
                    if token_key not in st.session_state:
                        st.session_state[token_key] = str(
                            uuid4()
                        )

                    with st.form(
                        f"cross_allocation_form_{nonce}",
                        clear_on_submit=False,
                    ):
                        origin_barangay_id = st.selectbox(
                            "Home / origin barangay *",
                            options=list(origin_by_id),
                            format_func=lambda barangay_id: (
                                origin_by_id[barangay_id]["name"]
                            ),
                        )

                        allocation_columns = st.columns(2)
                        allocation_families = (
                            allocation_columns[0].number_input(
                                "Families from origin barangay",
                                min_value=0,
                                step=1,
                            )
                        )
                        allocation_individuals = (
                            allocation_columns[1].number_input(
                                "Individuals from origin barangay",
                                min_value=0,
                                step=1,
                            )
                        )

                        st.caption(
                            "Enter 0 families / 0 individuals to clear "
                            "a previous allocation for the selected origin."
                        )

                        allocation_source = st.text_input(
                            "Information source *",
                            placeholder=(
                                "Camp manager, MSWDO, BDRRMC, "
                                "registration list"
                            ),
                        )

                        allocation_remarks = st.text_area(
                            "Remarks",
                            height=100,
                        )

                        allocation_confirm = st.checkbox(
                            "I verified that these evacuees normally "
                            "reside in the selected origin barangay."
                        )

                        allocation_submitted = (
                            st.form_submit_button(
                                "Save Cross-Barangay Allocation",
                                type="primary",
                                width="stretch",
                            )
                        )

                    if allocation_submitted:
                        if not allocation_confirm:
                            st.error(
                                "Confirm the origin before saving."
                            )
                        else:
                            try:
                                allocation_id = (
                                    create_cross_barangay_allocation(
                                        center_id=int(
                                            selected_cross_center_id
                                        ),
                                        origin_barangay_id=int(
                                            origin_barangay_id
                                        ),
                                        families=int(
                                            allocation_families
                                        ),
                                        individuals=int(
                                            allocation_individuals
                                        ),
                                        source=allocation_source,
                                        remarks=allocation_remarks,
                                        submission_key=st.session_state[
                                            token_key
                                        ],
                                        actor_user_id=current_user.id,
                                    )
                                )
                            except (
                                CrossBarangayValidationError,
                                CrossBarangayAuthorizationError,
                                CrossBarangayDataIntegrityError,
                                DuplicateCrossBarangaySubmissionError,
                                CrossBarangayServiceError,
                            ) as error:
                                st.error(str(error))
                            except Exception:
                                st.error(
                                    "The cross-barangay allocation "
                                    "could not be saved."
                                )
                            else:
                                st.session_state[
                                    "cross_allocation_nonce"
                                ] = nonce + 1
                                st.session_state.pop(
                                    token_key,
                                    None,
                                )
                                st.session_state[
                                    "evacuation_success"
                                ] = (
                                    "Cross-barangay allocation "
                                    f"#{allocation_id} saved."
                                )
                                st.rerun()

        render_dashboard_section_header(
            title="Current Cross-Barangay Allocations",
            subtitle=(
                "Active origin-to-host center allocations for the current event."
            ),
        )

        try:
            current_allocations = (
                list_current_cross_barangay_allocations()
            )
        except CrossBarangayServiceError as error:
            st.error(str(error))
            current_allocations = []

        if not current_allocations:
            st.info(
                "No active cross-barangay allocations are recorded."
            )
        else:
            routine_allocation_rows = [
                {
                    "Center": row["center_name"],
                    "Origin Barangay": row["origin_barangay_name"],
                    "Families": int(row["families"]),
                    "Individuals": int(row["individuals"]),
                    "Age": format_report_age(row["recorded_at"]),
                }
                for row in current_allocations
            ]

            st.dataframe(
                pd.DataFrame(routine_allocation_rows),
                width="stretch",
                hide_index=True,
                column_config={
                    "Center": st.column_config.TextColumn(
                        "Center",
                        width=220,
                        pinned=True,
                    ),
                    "Origin Barangay": st.column_config.TextColumn(
                        "Origin Barangay",
                        width=160,
                    ),
                    "Families": st.column_config.NumberColumn(
                        "Families",
                        width=80,
                        format="%d",
                    ),
                    "Individuals": st.column_config.NumberColumn(
                        "Individuals",
                        width=90,
                        format="%d",
                    ),
                    "Age": st.column_config.TextColumn(
                        "Age",
                        width=60,
                    ),
                },
            )

            with st.expander(
                "Full allocation source fields",
                expanded=False,
            ):
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Center": row["center_name"],
                                "Origin Barangay": (
                                    row["origin_barangay_name"]
                                ),
                                "Families": row["families"],
                                "Individuals": row["individuals"],
                                "Source": row["source"],
                                "Recorded By": row["recorded_by"],
                                "Recorded At": row["recorded_at"],
                            }
                            for row in current_allocations
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )


# ---------------------------------------------------------
# RECENT UPDATES
# ---------------------------------------------------------

with history_tab:
    render_dashboard_section_header(
        title="Recent Evacuation-Center Reports",
        subtitle=(
            "Routine view prioritizing center status, occupancy, essential "
            "services, medical demand, validation, and report age."
        ),
    )

    try:
        recent_updates = get_recent_evacuation_updates(limit=20)
    except EvacuationServiceError as error:
        st.error(str(error))
        recent_updates = []

    if not recent_updates:
        st.info("No evacuation-center reports have been saved.")
    else:
        routine_rows = [
            {
                "Center": update["center_name"],
                "Status": update["status"],
                "Occupancy F / I": (
                    f"{int(update['families']):,} / "
                    f"{int(update['individuals']):,}"
                ),
                "Services": (
                    f"{update['food_status']} · "
                    f"{update['water_status']} · "
                    f"{update['electricity_status']}"
                ),
                "Medical": int(update["medical_cases"]),
                "Validation": update["validation_status"],
                "Age": format_report_age(update["recorded_at"]),
            }
            for update in recent_updates
        ]

        st.dataframe(
            pd.DataFrame(routine_rows),
            width="stretch",
            hide_index=True,
            column_order=(
                "Center",
                "Status",
                "Occupancy F / I",
                "Services",
                "Medical",
                "Validation",
                "Age",
            ),
            column_config={
                "Center": st.column_config.TextColumn(
                    "Center",
                    width=230,
                    pinned=True,
                ),
                "Status": st.column_config.TextColumn(
                    "Status",
                    width=75,
                ),
                "Occupancy F / I": st.column_config.TextColumn(
                    "Occupancy F / I",
                    help="Registered families / registered individuals",
                    width=105,
                ),
                "Services": st.column_config.TextColumn(
                    "Food · Water · Power",
                    help=(
                        "Food status · water status · electricity status"
                    ),
                    width=205,
                ),
                "Medical": st.column_config.NumberColumn(
                    "Medical",
                    width=65,
                    format="%d",
                ),
                "Validation": st.column_config.TextColumn(
                    "Validation",
                    width=105,
                ),
                "Age": st.column_config.TextColumn(
                    "Age",
                    width=55,
                ),
            },
        )

        st.caption(
            "Host barangay and complete source fields are available below."
        )

        with st.expander(
            "Full recent report fields",
            expanded=False,
        ):
            full_rows = [
                {
                    "ID": update["id"],
                    "Center": update["center_name"],
                    "Barangay": update["barangay_name"],
                    "Status": update["status"],
                    "Families": update["families"],
                    "Individuals": update["individuals"],
                    "Children": update["children"],
                    "Senior Citizens": update["senior_citizens"],
                    "PWD": update["pwd"],
                    "Pregnant Women": update["pregnant_women"],
                    "Medical Cases": update["medical_cases"],
                    "Food": update["food_status"],
                    "Water": update["water_status"],
                    "Electricity": update["electricity_status"],
                    "Validation": update["validation_status"],
                    "Source": update["source"],
                    "Recorded At": update["recorded_at"],
                }
                for update in recent_updates
            ]

            st.dataframe(
                pd.DataFrame(full_rows),
                width="stretch",
                hide_index=True,
            )
