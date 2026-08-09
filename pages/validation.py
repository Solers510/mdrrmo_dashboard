from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

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
    review_barangay_update,
)
from config.access_control import (
    PERMISSION_VALIDATE_BARANGAY_REPORTS,
)
from utils.auth import require_permission


current_user = require_permission(
    PERMISSION_VALIDATE_BARANGAY_REPORTS
)

MANILA_TIMEZONE = ZoneInfo("Asia/Manila")


def format_datetime(
    value: datetime | None,
) -> str:
    if value is None:
        return "Not available"

    return value.astimezone(
        MANILA_TIMEZONE
    ).strftime(
        "%d %B %Y, %I:%M %p"
    )


st.title("Barangay Report Validation")

st.caption(
    "Review submitted barangay reports before they are "
    "included in the official validated dashboard."
)


success_message = st.session_state.pop(
    "validation_success",
    None,
)

if success_message:
    st.success(success_message)


# ---------------------------------------------------------
# ACTIVE EVENT
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
        "No active disaster event exists."
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


# ---------------------------------------------------------
# VALIDATION QUEUE
# ---------------------------------------------------------

try:
    queue = get_barangay_validation_queue()

except ValidationDataIntegrityError as error:
    st.error(str(error))
    st.stop()

except ValidationServiceError as error:
    st.error(str(error))
    st.stop()

except Exception as error:
    st.error(
        "An unexpected error occurred while loading "
        "the validation queue."
    )
    st.exception(error)
    st.stop()


st.subheader("Pending Reports")

st.metric(
    "Reports Awaiting Review",
    len(queue),
)


if not queue:
    st.success(
        "No barangay reports are currently waiting "
        "for validation."
    )
    st.stop()


queue_table = pd.DataFrame(
    [
        {
            "ID": record["id"],
            "Barangay": record["barangay_name"],
            "Situation": record["situation_status"],
            "Affected Families": (
                record["affected_families"]
            ),
            "Affected Individuals": (
                record["affected_individuals"]
            ),
            "Status": record["validation_status"],
            "Source": record["source"],
            "Recorded At": record["recorded_at"],
        }
        for record in queue
    ]
)

st.dataframe(
    queue_table,
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# SELECT REPORT
# ---------------------------------------------------------

record_by_id = {
    int(record["id"]): record
    for record in queue
}

report_ids = list(record_by_id.keys())


def report_label(report_id: int) -> str:
    report = record_by_id[report_id]

    return (
        f"#{report_id} — "
        f"{report['barangay_name']} — "
        f"{format_datetime(report['recorded_at'])}"
    )


selected_report_id = st.selectbox(
    "Select report to review",
    options=report_ids,
    format_func=report_label,
)

selected_report = record_by_id[
    selected_report_id
]


st.divider()

st.subheader(
    f"Report #{selected_report_id}: "
    f"{selected_report['barangay_name']}"
)


population_columns = st.columns(3)

with population_columns[0]:
    st.metric(
        "Affected Families",
        int(
            selected_report["affected_families"]
        ),
    )

with population_columns[1]:
    st.metric(
        "Affected Individuals",
        int(
            selected_report[
                "affected_individuals"
            ]
        ),
    )

with population_columns[2]:
    st.metric(
        "Rescue Requests",
        int(
            selected_report["rescue_requests"]
        ),
    )


evacuation_columns = st.columns(4)

with evacuation_columns[0]:
    st.metric(
        "Families Inside EC",
        int(
            selected_report[
                "inside_ec_families"
            ]
        ),
    )

with evacuation_columns[1]:
    st.metric(
        "Individuals Inside EC",
        int(
            selected_report[
                "inside_ec_individuals"
            ]
        ),
    )

with evacuation_columns[2]:
    st.metric(
        "Families Outside EC",
        int(
            selected_report[
                "outside_ec_families"
            ]
        ),
    )

with evacuation_columns[3]:
    st.metric(
        "Individuals Outside EC",
        int(
            selected_report[
                "outside_ec_individuals"
            ]
        ),
    )


condition_columns = st.columns(4)

with condition_columns[0]:
    st.write(
        "**Flood:**",
        selected_report["flood_status"],
    )

    st.write(
        "**Flood depth:**",
        f"{selected_report['flood_depth_cm']} cm",
    )

with condition_columns[1]:
    st.write(
        "**Road:**",
        selected_report["road_status"],
    )

with condition_columns[2]:
    st.write(
        "**Power:**",
        selected_report["power_status"],
    )

with condition_columns[3]:
    st.write(
        "**Water:**",
        selected_report["water_status"],
    )


st.write(
    "**Source:**",
    selected_report["source"],
)

st.write(
    "**Recorded at:**",
    format_datetime(
        selected_report["recorded_at"]
    ),
)

st.write(
    "**Remarks:**",
    selected_report["remarks"]
    or "No remarks provided.",
)


# ---------------------------------------------------------
# REVIEW FORM
# ---------------------------------------------------------

st.divider()

st.subheader("Review Decision")

with st.form(
    "barangay_validation_form",
    clear_on_submit=False,
):
    decision = st.radio(
        "Decision *",
        options=(
            "Validated",
            "Needs Correction",
        ),
        horizontal=True,
    )
    st.markdown("### Reviewer")

    st.info(
        f"{current_user.display_name} "
        f"— {current_user.role}"
    )
    st.caption(
        "Reviewer identity is taken automatically "
        "from the authenticated account."
    )


    review_notes = st.text_area(
        "Review notes",
        placeholder=(
            "Explain corrections, verification performed, "
            "or supporting references."
        ),
        height=130,
    )

    confirmation = st.checkbox(
        "I reviewed the figures, source, and supporting "
        "information for this report."
    )

    submitted = st.form_submit_button(
        "Save Review Decision",
        type="primary",
        use_container_width=True,
    )


if submitted:
    if not confirmation:
        st.error(
            "Confirm that the report was reviewed "
            "before saving."
        )

    else:
        try:
            review_barangay_update(
                update_id=int(selected_report_id),
                decision=decision,
                reviewer_user_id=current_user.id,
                review_notes=review_notes,
            )

        except ValidationInputError as error:
            st.error(str(error))

        except ReportAlreadyReviewedError as error:
            st.warning(str(error))

        except ValidationDataIntegrityError as error:
            st.error(str(error))

        except ValidationAuthorizationError as error:
            st.error(str(error))
        except ValidationServiceError as error:
            st.error(str(error))


        except Exception as error:
            st.error(
                "An unexpected database error occurred "
                "while saving the review."
            )
            st.exception(error)

        else:
            st.session_state[
                "validation_success"
            ] = (
                f"Report #{selected_report_id} "
                f"was marked {decision}."
            )

            st.rerun()