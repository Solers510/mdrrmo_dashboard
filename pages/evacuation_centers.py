from uuid import uuid4

import pandas as pd
import streamlit as st

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
    get_recent_evacuation_updates,
    list_active_evacuation_centers,
)
from config.access_control import (
    PERMISSION_MANAGE_EVACUATION_CENTERS,
    PERMISSION_SUBMIT_EVACUATION_UPDATES,
)
from utils.auth import has_permission, require_any_permission


current_user = require_any_permission(
    PERMISSION_MANAGE_EVACUATION_CENTERS,
    PERMISSION_SUBMIT_EVACUATION_UPDATES,
)


can_manage_centers = has_permission(
    current_user,
    PERMISSION_MANAGE_EVACUATION_CENTERS,
)

st.title("Evacuation Center Monitoring")

st.caption(
    "Manage evacuation-center records and preserve "
    "occupancy and service-condition updates."
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
    st.exception(error)
    st.stop()


if active_event is None:
    st.warning(
        "No active disaster event exists. Create one "
        "through Event Control first."
    )
    st.stop()


event_columns = st.columns(3)

with event_columns[0]:
    st.metric(
        "Active Event",
        str(active_event["event_name"]),
    )

with event_columns[1]:
    st.metric(
        "Alert Level",
        str(active_event["alert_code"]),
    )

with event_columns[2]:
    st.metric(
        "EOC Status",
        str(active_event["eoc_status"]),
    )


st.divider()


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


manage_tab, update_tab, cross_tab, history_tab = st.tabs(
    (
        "Manage Centers",
        "Record Occupancy Update",
        "Cross-Barangay Allocation",
        "Recent Updates",
    )
)


# ---------------------------------------------------------
# MANAGE CENTERS
# ---------------------------------------------------------

with manage_tab:
    st.subheader("Add Evacuation Center")

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
            "Official safe-capacity value",
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
            use_container_width=True,
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
                st.exception(error)

            else:
                st.session_state[
                    "evacuation_success"
                ] = (
                    f"Evacuation center #{center_id} "
                    "was created successfully."
                )

                st.rerun()

    st.subheader("Active Evacuation Centers")

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
                    "Address": center["address"],
                    "Safe Capacity": (
                        center["safe_capacity"]
                    ),
                }
                for center in centers
            ]
        )

        st.dataframe(
            center_table,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# OCCUPANCY UPDATE
# ---------------------------------------------------------

with update_tab:
    st.subheader("New Evacuation-Center Report")

    if not centers:
        st.warning(
            "Create at least one evacuation-center master "
            "record before recording an update."
        )

    else:
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

        with st.form(
            f"evacuation_update_form_{evacuation_update_form_nonce}",
            clear_on_submit=False,
        ):
            selected_center_label = st.selectbox(
                "Evacuation center *",
                options=center_labels,
            )

            status = st.selectbox(
                "Center status *",
                options=EVACUATION_CENTER_STATUSES,
            )

            st.markdown("### Occupancy")

            occupancy_columns = st.columns(2)

            with occupancy_columns[0]:
                families = st.number_input(
                    "Families",
                    min_value=0,
                    step=1,
                )

            with occupancy_columns[1]:
                individuals = st.number_input(
                    "Individuals",
                    min_value=0,
                    step=1,
                )

            st.markdown("### Vulnerable groups")

            vulnerable_row_1 = st.columns(3)

            with vulnerable_row_1[0]:
                children = st.number_input(
                    "Children",
                    min_value=0,
                    step=1,
                )

            with vulnerable_row_1[1]:
                senior_citizens = st.number_input(
                    "Senior citizens",
                    min_value=0,
                    step=1,
                )

            with vulnerable_row_1[2]:
                pwd = st.number_input(
                    "Persons with disabilities",
                    min_value=0,
                    step=1,
                )

            vulnerable_row_2 = st.columns(2)

            with vulnerable_row_2[0]:
                pregnant_women = st.number_input(
                    "Pregnant women",
                    min_value=0,
                    step=1,
                )

            with vulnerable_row_2[1]:
                medical_cases = st.number_input(
                    "Medical cases",
                    min_value=0,
                    step=1,
                )

            st.markdown("### Essential services")

            service_columns = st.columns(3)

            with service_columns[0]:
                food_status = st.selectbox(
                    "Food status",
                    options=SUPPLY_STATUSES,
                )

            with service_columns[1]:
                water_status = st.selectbox(
                    "Water status",
                    options=SUPPLY_STATUSES,
                )

            with service_columns[2]:
                electricity_status = st.selectbox(
                    "Electricity status",
                    options=ELECTRICITY_STATUSES,
                )

            sanitation_status = st.text_input(
                "Sanitation status *",
                placeholder=(
                    "Use the wording from the official form."
                ),
            )

            source = st.text_input(
                "Information source *",
                placeholder=(
                    "Camp manager, MSWDO, field team, "
                    "official center report"
                ),
            )

            remarks = st.text_area(
                "Remarks",
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
                use_container_width=True,
            )

        if update_submitted:
            if not confirmation:
                st.error(
                    "Confirm the report before saving."
                )

            else:
                selected_center_id = (
                    center_label_to_id[
                        selected_center_label
                    ]
                )

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
                    st.exception(error)

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
    st.subheader("Cross-Barangay Evacuation Allocation")

    st.caption(
        "Use this only when evacuees are staying in an evacuation "
        "center outside their home barangay. Normal barangay-to-own-center "
        "reporting does not require this form."
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
                occupancy_columns = st.columns(4)
                occupancy_columns[0].metric(
                    "Latest EC Families",
                    int(latest_update["families"]),
                )
                occupancy_columns[1].metric(
                    "Latest EC Individuals",
                    int(latest_update["individuals"]),
                )
                occupancy_columns[2].metric(
                    "Center Status",
                    str(latest_update["status"]),
                )
                occupancy_columns[3].metric(
                    "Current Foreign Origins",
                    len(cross_context["current_allocations"]),
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
                                use_container_width=True,
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

        st.markdown(
            "#### Current Cross-Barangay Allocations"
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
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Center": row["center_name"],
                            "Origin Barangay": row["origin_barangay_name"],
                            "Families": row["families"],
                            "Individuals": row["individuals"],
                            "Source": row["source"],
                            "Recorded By": row["recorded_by"],
                            "Recorded At": row["recorded_at"],
                        }
                        for row in current_allocations
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )


# ---------------------------------------------------------
# RECENT UPDATES
# ---------------------------------------------------------

with history_tab:
    st.subheader("Recent Evacuation-Center Updates")

    try:
        recent_updates = get_recent_evacuation_updates(
            limit=20
        )

    except EvacuationServiceError as error:
        st.error(str(error))
        recent_updates = []

    if not recent_updates:
        st.info(
            "No evacuation-center reports have been saved."
        )

    else:
        recent_table = pd.DataFrame(
            [
                {
                    "ID": update["id"],
                    "Center": update["center_name"],
                    "Barangay": update["barangay_name"],
                    "Status": update["status"],
                    "Families": update["families"],
                    "Individuals": update["individuals"],
                    "Children": update["children"],
                    "Senior Citizens": (
                        update["senior_citizens"]
                    ),
                    "PWD": update["pwd"],
                    "Pregnant Women": (
                        update["pregnant_women"]
                    ),
                    "Medical Cases": (
                        update["medical_cases"]
                    ),
                    "Food": update["food_status"],
                    "Water": update["water_status"],
                    "Electricity": (
                        update["electricity_status"]
                    ),
                    "Validation": (
                        update["validation_status"]
                    ),
                    "Source": update["source"],
                    "Recorded At": update["recorded_at"],
                }
                for update in recent_updates
            ]
        )

        st.dataframe(
            recent_table,
            use_container_width=True,
            hide_index=True,
        )
