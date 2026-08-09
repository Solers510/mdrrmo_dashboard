import pandas as pd
import streamlit as st

from config.constants import (
    FLOOD_STATUSES,
    ROAD_STATUSES,
    SITUATION_STATUSES,
    UTILITY_STATUSES,
)
from services.barangay_service import (
    BarangayDataIntegrityError,
    BarangayServiceError,
    BarangayValidationError,
    NoActiveEventError,
    create_barangay_update,
    get_recent_barangay_updates,
    list_active_barangays,
)
from services.event_service import (
    EventDataIntegrityError,
    get_active_event_summary,
)
from config.access_control import (
    PERMISSION_SUBMIT_BARANGAY_UPDATES,
)
from utils.auth import require_permission


current_user = require_permission(
    PERMISSION_SUBMIT_BARANGAY_UPDATES
)

st.title("Barangay Situation Update")

st.caption(
    "Record and preserve situation reports submitted "
    "by the barangays of Naic."
)


success_message = st.session_state.pop(
    "barangay_update_success",
    None,
)

if success_message:
    st.success(success_message)


# ---------------------------------------------------------
# LOAD ACTIVE EVENT
# ---------------------------------------------------------

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
        "No active disaster event exists. "
        "Create an event in Event Control before "
        "recording barangay updates."
    )
    st.stop()


event_column, alert_column, eoc_column = st.columns(3)

with event_column:
    st.metric(
        "Active Event",
        str(active_event["event_name"]),
    )

with alert_column:
    st.metric(
        "Alert Level",
        str(active_event["alert_code"]),
    )

with eoc_column:
    st.metric(
        "EOC Status",
        str(active_event["eoc_status"]),
    )


st.divider()


# ---------------------------------------------------------
# LOAD BARANGAYS
# ---------------------------------------------------------

try:
    barangay_records = list_active_barangays()

except BarangayServiceError as error:
    st.error(str(error))
    st.stop()

except Exception as error:
    st.error(
        "An unexpected error occurred while "
        "loading barangays."
    )
    st.exception(error)
    st.stop()


if not barangay_records:
    st.error(
        "No active barangays were found in PostgreSQL."
    )
    st.stop()


barangay_label_to_id = {
    f"{record['name']} — {record['psgc_code']}": int(
        record["id"]
    )
    for record in barangay_records
}

barangay_labels = list(
    barangay_label_to_id.keys()
)


st.caption(
    f"Active barangays loaded: {len(barangay_records)}"
)


# ---------------------------------------------------------
# DATA-ENTRY FORM
# ---------------------------------------------------------

st.subheader("New Barangay Report")

with st.form(
    "barangay_update_form",
    clear_on_submit=False,
):
    selected_barangay_label = st.selectbox(
        "Barangay *",
        options=barangay_labels,
    )

    situation_status = st.selectbox(
        "Situation status *",
        options=SITUATION_STATUSES,
        index=1,
    )

    st.markdown("### Affected population")

    affected_column_1, affected_column_2 = st.columns(2)

    with affected_column_1:
        affected_families = st.number_input(
            "Affected families",
            min_value=0,
            step=1,
        )

    with affected_column_2:
        affected_individuals = st.number_input(
            "Affected individuals",
            min_value=0,
            step=1,
        )

    st.markdown("### Inside evacuation centers")

    inside_column_1, inside_column_2 = st.columns(2)

    with inside_column_1:
        inside_ec_families = st.number_input(
            "Families inside evacuation centers",
            min_value=0,
            step=1,
        )

    with inside_column_2:
        inside_ec_individuals = st.number_input(
            "Individuals inside evacuation centers",
            min_value=0,
            step=1,
        )

    st.markdown("### Outside evacuation centers")

    outside_column_1, outside_column_2 = st.columns(2)

    with outside_column_1:
        outside_ec_families = st.number_input(
            "Families outside evacuation centers",
            min_value=0,
            step=1,
        )

    with outside_column_2:
        outside_ec_individuals = st.number_input(
            "Individuals outside evacuation centers",
            min_value=0,
            step=1,
        )

    st.markdown("### Hazard and utility conditions")

    hazard_column_1, hazard_column_2 = st.columns(2)

    with hazard_column_1:
        flood_status = st.selectbox(
            "Flood status",
            options=FLOOD_STATUSES,
        )

        flood_depth_cm = st.number_input(
            "Estimated flood depth in centimeters",
            min_value=0.0,
            step=1.0,
            format="%.2f",
        )

        road_status = st.selectbox(
            "Road status",
            options=ROAD_STATUSES,
        )

    with hazard_column_2:
        power_status = st.selectbox(
            "Power status",
            options=UTILITY_STATUSES,
        )

        water_status = st.selectbox(
            "Water status",
            options=UTILITY_STATUSES,
        )

        rescue_requests = st.number_input(
            "Pending rescue requests",
            min_value=0,
            step=1,
        )

    st.markdown("### Source and documentation")

    source = st.text_input(
        "Information source *",
        placeholder=(
            "Example: Barangay Captain, BDRRMC radio, "
            "field responder, official report"
        ),
    )

    remarks = st.text_area(
        "Remarks",
        placeholder=(
            "Add relevant conditions, explanations, "
            "locations, or data limitations."
        ),
        height=120,
    )

    st.info(
        "This report will be saved with the "
        "validation status: Submitted."
    )

    confirmation = st.checkbox(
        "I reviewed the figures and source before submission."
    )

    submitted = st.form_submit_button(
        "Save Barangay Update",
        type="primary",
        use_container_width=True,
    )


if submitted:
    selected_barangay_id = barangay_label_to_id[
        selected_barangay_label
    ]

    if not confirmation:
        st.error(
            "Review and confirm the report before saving."
        )

    else:
        try:
            update_id = create_barangay_update(
                barangay_id=selected_barangay_id,
                situation_status=situation_status,
                affected_families=int(
                    affected_families
                ),
                affected_individuals=int(
                    affected_individuals
                ),
                inside_ec_families=int(
                    inside_ec_families
                ),
                inside_ec_individuals=int(
                    inside_ec_individuals
                ),
                outside_ec_families=int(
                    outside_ec_families
                ),
                outside_ec_individuals=int(
                    outside_ec_individuals
                ),
                flood_status=flood_status,
                flood_depth_cm=float(
                    flood_depth_cm
                ),
                road_status=road_status,
                power_status=power_status,
                water_status=water_status,
                rescue_requests=int(
                    rescue_requests
                ),
                source=source,
                remarks=remarks,
            )

        except NoActiveEventError as error:
            st.warning(str(error))

        except BarangayValidationError as error:
            st.error(str(error))

        except BarangayDataIntegrityError as error:
            st.error(str(error))

        except BarangayServiceError as error:
            st.error(str(error))

        except Exception as error:
            st.error(
                "An unexpected database error occurred "
                "while saving the barangay update."
            )
            st.exception(error)

        else:
            st.session_state[
                "barangay_update_success"
            ] = (
                f"Barangay update #{update_id} "
                "was saved successfully."
            )

            st.rerun()


# ---------------------------------------------------------
# RECENT REPORTS
# ---------------------------------------------------------

st.divider()

st.subheader("Recent Barangay Updates")

try:
    recent_updates = get_recent_barangay_updates(
        limit=20
    )

except BarangayServiceError as error:
    st.error(str(error))
    recent_updates = []

except Exception as error:
    st.error(
        "Recent barangay updates could not be loaded."
    )
    st.exception(error)
    recent_updates = []


if not recent_updates:
    st.info(
        "No barangay updates have been recorded "
        "for the active event."
    )

else:
    table_rows = []

    for record in recent_updates:
        table_rows.append(
            {
                "ID": record["id"],
                "Barangay": record["barangay_name"],
                "Status": record["situation_status"],
                "Affected Families": (
                    record["affected_families"]
                ),
                "Affected Individuals": (
                    record["affected_individuals"]
                ),
                "Inside EC": (
                    record["inside_ec_individuals"]
                ),
                "Outside EC": (
                    record["outside_ec_individuals"]
                ),
                "Road": record["road_status"],
                "Power": record["power_status"],
                "Water": record["water_status"],
                "Rescue Requests": (
                    record["rescue_requests"]
                ),
                "Validation": (
                    record["validation_status"]
                ),
                "Source": record["source"],
                "Recorded At": record["recorded_at"],
            }
        )

    dataframe = pd.DataFrame(table_rows)

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )