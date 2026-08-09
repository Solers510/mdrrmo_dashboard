from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from config.access_control import (
    PERMISSION_SUBMIT_BARANGAY_UPDATES,
)
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
    DuplicateBarangaySubmissionError,
    NoActiveEventError,
    create_barangay_update,
    get_barangay_entry_context,
    get_recent_barangay_updates,
    list_active_barangays,
)
from services.data_integrity import (
    DataIntegrityValidationError,
    reconcile_population,
    validate_flood_consistency,
)
from services.event_service import (
    EventDataIntegrityError,
    get_active_event_summary,
)
from utils.auth import require_permission


current_user = require_permission(
    PERMISSION_SUBMIT_BARANGAY_UPDATES
)

MANILA_TIMEZONE = ZoneInfo("Asia/Manila")


def format_datetime(
    value: datetime | None,
) -> str:
    if value is None:
        return "No evacuation-center report yet"

    return value.astimezone(
        MANILA_TIMEZONE
    ).strftime(
        "%d %B %Y, %I:%M %p"
    )


st.title("Barangay Situation Update")

st.caption(
    "Record affected, inside-evacuation, and outside-evacuation figures. "
    "The latest evacuation-center totals are prefilled as a reference, "
    "but the barangay encoder can enter a newer verified count."
)


success_message = st.session_state.pop(
    "barangay_update_success",
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
    st.warning(
        "No active disaster event exists. Create an "
        "event in Event Control before recording reports."
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


try:
    barangay_records = list_active_barangays()

except BarangayServiceError as error:
    st.error(str(error))
    st.stop()


if not barangay_records:
    st.error(
        "No active barangays were found."
    )
    st.stop()


barangay_label_to_id = {
    (
        f"{record['name']} — "
        f"{record['psgc_code']}"
    ): int(record["id"])
    for record in barangay_records
}

barangay_labels = list(
    barangay_label_to_id
)


st.divider()

st.subheader("New Barangay Report")

st.caption(
    f"Submitting as {current_user.display_name} "
    f"— {current_user.role}"
)


nonce = int(
    st.session_state.setdefault(
        "barangay_form_nonce",
        0,
    )
)

selector_key = (
    f"barangay_{nonce}_barangay"
)

token_state_key = (
    f"barangay_submission_key_{nonce}"
)

if token_state_key not in st.session_state:
    st.session_state[
        token_state_key
    ] = str(uuid4())


selected_label = st.selectbox(
    "Barangay *",
    options=barangay_labels,
    key=selector_key,
)

selected_barangay_id = (
    barangay_label_to_id[
        selected_label
    ]
)

# Scope data-entry widget state to both the report generation and
# selected barangay. This prevents figures typed for one barangay
# from silently carrying over when the user changes the selection.
prefix = (
    f"barangay_{nonce}_"
    f"{selected_barangay_id}_"
)


try:
    entry_context = (
        get_barangay_entry_context(
            barangay_id=selected_barangay_id
        )
    )

except BarangayServiceError as error:
    st.error(str(error))
    st.stop()


st.markdown(
    "### Inside evacuation centers"
)

st.caption(
    "Latest evacuation-center records are used as the default. "
    "If the barangay has a newer verified count, update the fields below. "
    "A difference is flagged for reconciliation instead of blocking entry."
)

reference_columns = st.columns(3)

with reference_columns[0]:
    st.metric(
        "Latest EC record — families",
        int(
            entry_context[
                "inside_ec_families"
            ]
        ),
    )

with reference_columns[1]:
    st.metric(
        "Latest EC record — individuals",
        int(
            entry_context[
                "inside_ec_individuals"
            ]
        ),
    )

with reference_columns[2]:
    st.metric(
        "Operational centers",
        int(
            entry_context[
                "operational_centers"
            ]
        ),
    )

st.caption(
    "Latest EC data: "
    + format_datetime(
        entry_context[
            "latest_ec_update"
        ]
    )
)

inside_columns = st.columns(2)

with inside_columns[0]:
    inside_ec_families = st.number_input(
        "Families inside evacuation centers",
        min_value=0,
        step=1,
        value=int(
            entry_context[
                "inside_ec_families"
            ]
        ),
        key=prefix + "inside_families",
    )

with inside_columns[1]:
    inside_ec_individuals = st.number_input(
        "Individuals inside evacuation centers",
        min_value=0,
        step=1,
        value=int(
            entry_context[
                "inside_ec_individuals"
            ]
        ),
        key=prefix + "inside_individuals",
    )

ec_reference_mismatch = (
    int(inside_ec_families)
    != int(
        entry_context[
            "inside_ec_families"
        ]
    )
    or int(inside_ec_individuals)
    != int(
        entry_context[
            "inside_ec_individuals"
        ]
    )
)

if ec_reference_mismatch:
    st.warning(
        "The barangay Inside-EC figures differ from the latest "
        "evacuation-center records. This is allowed when the barangay "
        "has newer verified information. The difference should be "
        "checked during validation."
    )


st.markdown(
    "### Affected population"
)

affected_columns = st.columns(2)

with affected_columns[0]:
    affected_families = st.number_input(
        "Affected families",
        min_value=0,
        step=1,
        key=(
            prefix
            + "affected_families"
        ),
    )

with affected_columns[1]:
    affected_individuals = st.number_input(
        "Affected individuals",
        min_value=0,
        step=1,
        key=(
            prefix
            + "affected_individuals"
        ),
    )


st.markdown(
    "### Outside evacuation centers"
)

outside_columns = st.columns(2)

with outside_columns[0]:
    outside_ec_families = st.number_input(
        "Families outside evacuation centers",
        min_value=0,
        step=1,
        key=(
            prefix
            + "outside_families"
        ),
    )

with outside_columns[1]:
    outside_ec_individuals = (
        st.number_input(
            "Individuals outside evacuation centers",
            min_value=0,
            step=1,
            key=(
                prefix
                + "outside_individuals"
            ),
        )
    )


preview_error = None
reconciliation = None

try:
    reconciliation = reconcile_population(
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
    )

except DataIntegrityValidationError as error:
    preview_error = str(error)


st.markdown(
    "### Population reconciliation"
)

if reconciliation is not None:
    reconciliation_columns = (
        st.columns(4)
    )

    with reconciliation_columns[0]:
        st.metric(
            "Displaced families",
            reconciliation.displaced_families,
        )

    with reconciliation_columns[1]:
        st.metric(
            "Displaced individuals",
            reconciliation.displaced_individuals,
        )

    with reconciliation_columns[2]:
        st.metric(
            "Affected, not displaced — families",
            reconciliation.remaining_families,
        )

    with reconciliation_columns[3]:
        st.metric(
            "Affected, not displaced — individuals",
            reconciliation.remaining_individuals,
        )

    st.success(
        "Population figures are internally consistent."
    )

else:
    st.error(preview_error)


situation_status = st.selectbox(
    "Situation status *",
    options=SITUATION_STATUSES,
    index=min(
        2,
        len(SITUATION_STATUSES) - 1,
    ),
    key=prefix + "situation_status",
)


st.markdown(
    "### Hazard and utility conditions"
)

hazard_columns = st.columns(2)

with hazard_columns[0]:
    flood_status = st.selectbox(
        "Flood status",
        options=FLOOD_STATUSES,
        key=prefix + "flood_status",
    )

    flood_depth_cm = st.number_input(
        "Estimated flood depth in centimeters",
        min_value=0.0,
        step=1.0,
        format="%.2f",
        key=prefix + "flood_depth",
    )

    road_status = st.selectbox(
        "Road status",
        options=ROAD_STATUSES,
        key=prefix + "road_status",
    )

with hazard_columns[1]:
    power_status = st.selectbox(
        "Power status",
        options=UTILITY_STATUSES,
        key=prefix + "power_status",
    )

    water_status = st.selectbox(
        "Water status",
        options=UTILITY_STATUSES,
        key=prefix + "water_status",
    )

    rescue_requests = st.number_input(
        "Pending rescue requests",
        min_value=0,
        step=1,
        key=prefix + "rescue_requests",
    )


flood_error = None

try:
    validate_flood_consistency(
        flood_status=flood_status,
        flood_depth_cm=float(
            flood_depth_cm
        ),
    )

except DataIntegrityValidationError as error:
    flood_error = str(error)
    st.error(flood_error)


source = st.text_input(
    "Information source *",
    placeholder=(
        "Barangay Captain, BDRRMC radio, "
        "field responder, official report"
    ),
    key=prefix + "source",
)

remarks = st.text_area(
    "Remarks",
    height=120,
    key=prefix + "remarks",
)

confirmation = st.checkbox(
    "I reviewed the figures and source "
    "before submission.",
    key=prefix + "confirmation",
)


can_submit = (
    preview_error is None
    and flood_error is None
    and bool(source.strip())
    and confirmation
)


if st.button(
    "Save Barangay Report",
    type="primary",
    use_container_width=True,
    disabled=not can_submit,
    key=prefix + "submit",
):
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
            submission_key=(
                st.session_state[
                    token_state_key
                ]
            ),
            submitter_user_id=(
                current_user.id
            ),
        )

    except (
        NoActiveEventError,
        BarangayValidationError,
        BarangayDataIntegrityError,
        DuplicateBarangaySubmissionError,
        BarangayServiceError,
    ) as error:
        st.error(str(error))

    except Exception:
        st.error(
            "The report could not be saved. "
            "Your entered values were kept; "
            "try again or contact the system administrator."
        )

    else:
        st.session_state[
            "barangay_update_success"
        ] = (
            f"Barangay report #{update_id} "
            "was saved successfully."
        )

        st.session_state[
            "barangay_form_nonce"
        ] = nonce + 1

        st.session_state.pop(
            token_state_key,
            None,
        )

        st.rerun()


st.divider()

st.subheader(
    "Recent Barangay Reports"
)


try:
    recent_updates = (
        get_recent_barangay_updates(
            limit=20
        )
    )

except BarangayServiceError as error:
    st.error(str(error))
    recent_updates = []


if not recent_updates:
    st.info(
        "No barangay reports have been "
        "recorded for the active event."
    )

else:
    table_rows = [
        {
            "ID": row["id"],
            "Barangay": row["barangay_name"],
            "Situation": row[
                "situation_status"
            ],
            "Affected Families": row[
                "affected_families"
            ],
            "Affected Individuals": row[
                "affected_individuals"
            ],
            "Inside EC": row[
                "inside_ec_individuals"
            ],
            "Outside EC": row[
                "outside_ec_individuals"
            ],
            "Rescue Requests": row[
                "rescue_requests"
            ],
            "Validation": row[
                "validation_status"
            ],
            "Source": row["source"],
            "Recorded At": row[
                "recorded_at"
            ],
        }
        for row in recent_updates
    ]

    st.dataframe(
        pd.DataFrame(table_rows),
        use_container_width=True,
        hide_index=True,
    )
