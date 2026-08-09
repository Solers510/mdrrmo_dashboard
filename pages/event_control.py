from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from config.constants import EOC_STATUSES, HAZARD_TYPES
from services.event_service import (
    ActiveEventAlreadyExistsError,
    EventDataIntegrityError,
    EventServiceError,
    EventValidationError,
    create_event,
    get_active_event_summary,
    list_alert_levels,
)
from config.access_control import (
    PERMISSION_MANAGE_EVENTS,
)
from utils.auth import require_permission


current_user = require_permission(
    PERMISSION_MANAGE_EVENTS
)

MANILA_TIMEZONE = ZoneInfo("Asia/Manila")


def format_datetime(value: datetime | None) -> str:
    """
    Convert a stored datetime to a readable Manila timestamp.
    """
    if value is None:
        return "Not provided"

    localized = value.astimezone(MANILA_TIMEZONE)

    return localized.strftime(
        "%d %B %Y, %I:%M %p"
    )


st.title("Event Control")

st.caption(
    "Create and manage the current disaster event, "
    "operational alert level, EOC status, and reporting period."
)


# Display a message after the page reruns.
success_message = st.session_state.pop(
    "event_control_success",
    None,
)

if success_message:
    st.success(success_message)


# Load database data.
try:
    alert_levels = list_alert_levels()
    active_event = get_active_event_summary()

except EventDataIntegrityError as error:
    st.error(str(error))
    st.stop()

except Exception as error:
    st.error(
        "The Event Control page could not retrieve data "
        "from PostgreSQL."
    )

    # Useful during development. Remove technical details
    # from the production version.
    st.exception(error)
    st.stop()


if not alert_levels:
    st.error(
        "No active alert-level records were found. "
        "Run the master-data seed script."
    )
    st.code(
        "python -m scripts.seed_master_data",
        language="powershell",
    )
    st.stop()


# ---------------------------------------------------------
# ACTIVE EVENT DISPLAY
# ---------------------------------------------------------

if active_event is not None:
    st.subheader("Current Active Event")

    column_1, column_2, column_3, column_4 = st.columns(4)

    with column_1:
        st.metric(
            label="Event",
            value=str(active_event["event_name"]),
        )

    with column_2:
        st.metric(
            label="Alert Level",
            value=str(active_event["alert_code"]),
        )

    with column_3:
        st.metric(
            label="EOC Status",
            value=str(active_event["eoc_status"]),
        )

    with column_4:
        st.metric(
            label="Hazard",
            value=str(active_event["hazard_type"]),
        )

    st.divider()

    detail_column_1, detail_column_2 = st.columns(2)

    with detail_column_1:
        st.markdown("#### Event details")

        st.write(
            "**Started:**",
            format_datetime(active_event["started_at"]),
        )

        st.write(
            "**SitRep number:**",
            active_event["current_sitrep_number"]
            or "Not provided",
        )

        st.write(
            "**Official reference:**",
            active_event["official_reference"]
            or "Not provided",
        )

    with detail_column_2:
        st.markdown("#### Situation overview")

        st.write(
            active_event["situation_overview"]
            or "No situation overview has been entered."
        )

    st.info(
        "A current active event already exists. "
        "The event-closing and alert-change functions "
        "will be added in the next phases."
    )

    # Stop here so the create-event form is not displayed.
    st.stop()


# ---------------------------------------------------------
# CREATE EVENT FORM
# ---------------------------------------------------------

st.subheader("Create Active Event")

st.info(
    "No active disaster event currently exists. "
    "Complete the form below to create one."
)


alert_label_to_code = {
    f"{record['name']} — {record['code']}": record["code"]
    for record in alert_levels
}

alert_labels = list(alert_label_to_code.keys())

current_time = datetime.now(MANILA_TIMEZONE)

default_date = current_time.date()

default_time = current_time.time().replace(
    second=0,
    microsecond=0,
    tzinfo=None,
)


with st.form(
    "create_event_form",
    clear_on_submit=False,
):
    st.markdown("### Basic event information")

    event_name = st.text_input(
        "Event name *",
        placeholder="Example: Tropical Depression Luis",
        help=(
            "Use the official or locally adopted event name."
        ),
    )

    hazard_type = st.selectbox(
        "Hazard type *",
        options=HAZARD_TYPES,
    )

    selected_alert_label = st.selectbox(
        "Initial alert level *",
        options=alert_labels,
        help=(
            "Select the officially declared operational "
            "alert level."
        ),
    )

    eoc_status = st.selectbox(
        "EOC status *",
        options=EOC_STATUSES,
    )

    st.markdown("### Effective date and time")

    date_column, time_column = st.columns(2)

    with date_column:
        start_date = st.date_input(
            "Start date *",
            value=default_date,
        )

    with time_column:
        start_time = st.time_input(
            "Start time *",
            value=default_time,
        )

    st.markdown("### Reporting information")

    current_sitrep_number = st.text_input(
        "Current SitRep number",
        placeholder="Example: SitRep No. 1",
    )

    official_reference = st.text_input(
        "Official event reference",
        placeholder=(
            "Bulletin, memorandum, advisory, "
            "executive order, or reference number"
        ),
    )

    situation_overview = st.text_area(
        "Initial situation overview",
        placeholder=(
            "Enter the initial operational situation "
            "and known conditions."
        ),
        height=150,
    )

    st.markdown("### Alert-level documentation")

    initial_alert_reason = st.text_area(
        "Reason for initial alert level *",
        placeholder=(
            "State why this alert level is in effect. "
            "Do not rely only on the color or label."
        ),
        height=120,
    )

    authority_reference = st.text_input(
        "Declaring authority or reference",
        placeholder=(
            "Name, position, office order, "
            "memorandum, or other authority"
        ),
    )

    confirmation = st.checkbox(
        "I confirm that the entered event and alert "
        "information reflects the authorized operational record."
    )

    submitted = st.form_submit_button(
        "Create Active Event",
        type="primary",
        use_container_width=True,
    )


if submitted:
    validation_errors: list[str] = []

    if not event_name.strip():
        validation_errors.append(
            "Event name is required."
        )

    if not initial_alert_reason.strip():
        validation_errors.append(
            "Reason for the initial alert level is required."
        )

    if not confirmation:
        validation_errors.append(
            "You must confirm the operational record "
            "before saving."
        )

    if validation_errors:
        for validation_error in validation_errors:
            st.error(validation_error)

    else:
        selected_alert_code = alert_label_to_code[
            selected_alert_label
        ]

        started_at = datetime.combine(
            start_date,
            start_time,
        ).replace(
            tzinfo=MANILA_TIMEZONE
        )

        try:
            event_id = create_event(
                event_name=event_name,
                hazard_type=hazard_type,
                alert_code=selected_alert_code,
                eoc_status=eoc_status,
                started_at=started_at,
                current_sitrep_number=current_sitrep_number,
                official_reference=official_reference,
                situation_overview=situation_overview,
                initial_alert_reason=initial_alert_reason,
                authority_reference=authority_reference,
            )

        except ActiveEventAlreadyExistsError as error:
            st.warning(str(error))

        except EventValidationError as error:
            st.error(str(error))

        except EventServiceError as error:
            st.error(str(error))

        except Exception as error:
            st.error(
                "An unexpected database error occurred "
                "while creating the event."
            )
            st.exception(error)

        else:
            st.session_state["event_control_success"] = (
                f"Event #{event_id} was created successfully."
            )

            st.rerun()