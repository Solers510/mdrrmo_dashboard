from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from services.dashboard_service import (
    DashboardDataIntegrityError,
    DashboardServiceError,
    get_dashboard_bundle,
)


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")


ALERT_STYLES = {
    "WHITE": {
        "background": "#F3F4F6",
        "border": "#9CA3AF",
        "text": "#111827",
    },
    "BLUE": {
        "background": "#DBEAFE",
        "border": "#2563EB",
        "text": "#1E3A8A",
    },
    "RED": {
        "background": "#FEE2E2",
        "border": "#DC2626",
        "text": "#7F1D1D",
    },
}


def format_datetime(
    value: datetime | None,
) -> str:
    """
    Display a database timestamp in Manila time.
    """
    if value is None:
        return "No reports recorded"

    localized = value.astimezone(
        MANILA_TIMEZONE
    )

    return localized.strftime(
        "%d %B %Y, %I:%M:%S %p"
    )


def render_alert_banner(
    *,
    alert_code: str,
    event_name: str,
    eoc_status: str,
) -> None:
    """
    Display an alert banner using text and color.
    """
    style = ALERT_STYLES.get(
        alert_code,
        ALERT_STYLES["WHITE"],
    )

    safe_alert = escape(alert_code)
    safe_event = escape(event_name)
    safe_eoc = escape(eoc_status)

    st.markdown(
        f"""
        <div style="
            background: {style['background']};
            border-left: 8px solid {style['border']};
            color: {style['text']};
            padding: 18px 22px;
            border-radius: 8px;
            margin-bottom: 18px;
        ">
            <div style="
                font-size: 1.45rem;
                font-weight: 700;
            ">
                {safe_alert} ALERT
            </div>
            <div style="
                font-size: 1rem;
                margin-top: 4px;
            ">
                {safe_event} · EOC: {safe_eoc}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_summary_cards(
    summary: dict[str, object],
) -> None:
    """
    Render the primary dashboard figures.
    """
    row_1 = st.columns(4)

    with row_1[0]:
        st.metric(
            "Affected Barangays",
            int(summary["affected_barangays"]),
        )

    with row_1[1]:
        st.metric(
            "Affected Families",
            f"{int(summary['affected_families']):,}",
        )

    with row_1[2]:
        st.metric(
            "Affected Individuals",
            f"{int(summary['affected_individuals']):,}",
        )

    with row_1[3]:
        st.metric(
            "Pending Rescue Requests",
            int(
                summary[
                    "pending_rescue_requests"
                ]
            ),
        )

    row_2 = st.columns(4)

    with row_2[0]:
        st.metric(
            "Inside Evacuation Centers",
            f"{int(summary['inside_ec_individuals']):,}",
            help="Current reported individuals inside ECs.",
        )

    with row_2[1]:
        st.metric(
            "Outside Evacuation Centers",
            f"{int(summary['outside_ec_individuals']):,}",
            help=(
                "Current reported displaced individuals "
                "outside formal evacuation centers."
            ),
        )

    with row_2[2]:
        st.metric(
            "Impassable Roads",
            int(summary["impassable_roads"]),
        )

    with row_2[3]:
        st.metric(
            "Barangays Without Reports",
            int(summary["missing_reports"]),
        )


st.title("MDRRMO Naic Situation Dashboard")

st.caption(
    "Current operational figures derived from the latest "
    "barangay report for each barangay."
)


refresh_clicked = st.button(
    "Refresh Dashboard",
)

if refresh_clicked:
    st.rerun()


try:
    dashboard = get_dashboard_bundle()

except DashboardDataIntegrityError as error:
    st.error(str(error))
    st.stop()

except DashboardServiceError as error:
    st.error(str(error))
    st.stop()

except Exception as error:
    st.error(
        "An unexpected error occurred while loading "
        "the dashboard."
    )
    st.exception(error)
    st.stop()


active_event = dashboard["active_event"]

if active_event is None:
    st.warning(
        "No active disaster event exists. "
        "Create an event through Event Control first."
    )
    st.stop()


render_alert_banner(
    alert_code=str(active_event["alert_code"]),
    event_name=str(active_event["event_name"]),
    eoc_status=str(active_event["eoc_status"]),
)


view_mode = st.radio(
    "Dashboard data mode",
    options=(
        "Provisional Operational",
        "Official Validated",
    ),
    horizontal=True,
    help=(
        "Provisional uses submitted operational reports. "
        "Official uses validated reports only."
    ),
)


if view_mode == "Provisional Operational":
    summary = dashboard["provisional_summary"]
    selected_rows = dashboard["provisional_rows"]

    st.warning(
        "This view includes submitted reports that may "
        "not yet have completed formal validation."
    )

else:
    summary = dashboard["official_summary"]
    selected_rows = dashboard["official_rows"]

    st.success(
        "This view uses only records marked Validated."
    )


if summary is None:
    st.info(
        "No dashboard summary is currently available."
    )
    st.stop()


render_summary_cards(summary)


st.divider()


# ---------------------------------------------------------
# REPORT COVERAGE
# ---------------------------------------------------------

st.subheader("Reporting Coverage")

coverage_columns = st.columns(4)

with coverage_columns[0]:
    st.metric(
        "Total Barangays",
        int(summary["total_barangays"]),
    )

with coverage_columns[1]:
    st.metric(
        "Reports Received",
        int(summary["reports_received"]),
    )

with coverage_columns[2]:
    st.metric(
        "Reports Included",
        int(summary["usable_reports"]),
    )

with coverage_columns[3]:
    st.metric(
        "Needs Correction",
        int(summary["needs_correction"]),
    )


st.write(
    "**Latest report timestamp:**",
    format_datetime(
        summary["latest_update"]
    ),
)


st.divider()


# ---------------------------------------------------------
# CURRENT BARANGAY TABLE
# ---------------------------------------------------------

st.subheader("Latest Barangay Situation")

if not selected_rows:
    if view_mode == "Official Validated":
        st.info(
            "No validated barangay reports are available. "
            "This is expected until a validation workflow "
            "has been implemented."
        )
    else:
        st.info(
            "No barangay reports have been submitted for "
            "the active event."
        )

else:
    table_rows = []

    for record in selected_rows:
        table_rows.append(
            {
                "Barangay": record["barangay_name"],
                "Situation": (
                    record["situation_status"]
                ),
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
                "Flood": record["flood_status"],
                "Flood Depth (cm)": (
                    record["flood_depth_cm"]
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
                "Recorded At": (
                    record["recorded_at"]
                ),
            }
        )

    dataframe = pd.DataFrame(
        table_rows
    )

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )


st.divider()


# ---------------------------------------------------------
# AFFECTED POPULATION CHART
# ---------------------------------------------------------

st.subheader("Affected Individuals by Barangay")

if not selected_rows:
    st.info(
        "No barangay data is available for this chart."
    )

else:
    chart_rows = [
        {
            "Barangay": record["barangay_name"],
            "Affected Individuals": int(
                record["affected_individuals"]
            ),
        }
        for record in selected_rows
        if int(
            record["affected_individuals"]
        ) > 0
    ]

    if not chart_rows:
        st.info(
            "No affected individuals are currently "
            "reported in this view."
        )

    else:
        chart_dataframe = (
            pd.DataFrame(chart_rows)
            .set_index("Barangay")
        )

        st.bar_chart(
            chart_dataframe,
            use_container_width=True,
        )


st.divider()


# ---------------------------------------------------------
# OPERATIONAL INTERRUPTIONS
# ---------------------------------------------------------

st.subheader("Operational Interruptions")

interruption_columns = st.columns(3)

with interruption_columns[0]:
    st.metric(
        "Impassable Roads",
        int(summary["impassable_roads"]),
    )

with interruption_columns[1]:
    st.metric(
        "Power Interrupted",
        int(summary["interrupted_power"]),
    )

with interruption_columns[2]:
    st.metric(
        "Water Interrupted",
        int(summary["interrupted_water"]),
    )