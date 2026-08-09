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


manage_tab, update_tab, history_tab = st.tabs(
    (
        "Manage Centers",
        "Record Occupancy Update",
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
                "The report will be saved with the status "
                "Submitted until evacuation validation is added."
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
