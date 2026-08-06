from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st

from services.dashboard_service import (
    DashboardDataIntegrityError,
    DashboardServiceError,
    get_dashboard_bundle,
)


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

PROVISIONAL_INCLUDED_STATUSES = {
    "Submitted",
    "For Validation",
    "Validated",
}


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
    Render the primary barangay dashboard figures.
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
            int(summary["pending_rescue_requests"]),
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


def record_is_included(
    record: dict[str, object],
    *,
    view_mode: str,
) -> bool:
    """
    Determine whether a record contributes to the selected
    dashboard mode.
    """
    validation_status = str(
        record["validation_status"]
    )

    if view_mode == "Official Validated":
        return validation_status == "Validated"

    return validation_status in PROVISIONAL_INCLUDED_STATUSES


st.title("MDRRMO Naic Situation Dashboard")

st.caption(
    "Current operational figures derived from the latest "
    "barangay and evacuation-center reports."
)


if st.button("Refresh Dashboard"):
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

    evacuation_summary = dashboard[
        "provisional_evacuation_summary"
    ]
    evacuation_rows = dashboard[
        "provisional_evacuation_rows"
    ]

    st.warning(
        "This view includes submitted operational reports "
        "that may not yet have completed formal validation."
    )

else:
    summary = dashboard["official_summary"]
    selected_rows = dashboard["official_rows"]

    evacuation_summary = dashboard[
        "official_evacuation_summary"
    ]
    evacuation_rows = dashboard[
        "official_evacuation_rows"
    ]

    st.success(
        "This view uses only records marked Validated."
    )


if summary is None:
    st.info(
        "No barangay dashboard summary is currently available."
    )
    st.stop()

if evacuation_summary is None:
    st.info(
        "No evacuation-center summary is currently available."
    )
    st.stop()


included_barangay_rows = [
    record
    for record in selected_rows
    if record_is_included(
        record,
        view_mode=view_mode,
    )
]

included_evacuation_rows = [
    record
    for record in evacuation_rows
    if record_is_included(
        record,
        view_mode=view_mode,
    )
]


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
    "**Latest barangay report timestamp:**",
    format_datetime(summary["latest_update"]),
)


st.divider()


# ---------------------------------------------------------
# CURRENT BARANGAY TABLE
# ---------------------------------------------------------

st.subheader("Latest Barangay Situation")

if not selected_rows:
    if view_mode == "Official Validated":
        st.info(
            "No validated barangay reports are available "
            "for the active event."
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
                "Situation": record["situation_status"],
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

    dataframe = pd.DataFrame(table_rows)

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

affected_chart_rows = [
    {
        "Barangay": record["barangay_name"],
        "Affected Individuals": int(
            record["affected_individuals"]
        ),
    }
    for record in included_barangay_rows
    if int(record["affected_individuals"]) > 0
]

if not affected_chart_rows:
    st.info(
        "No affected individuals are currently reported "
        "in this dashboard mode."
    )

else:
    affected_dataframe = (
        pd.DataFrame(affected_chart_rows)
        .sort_values(
            "Affected Individuals",
            ascending=False,
        )
        .head(10)
        .sort_values(
            "Affected Individuals",
            ascending=True,
        )
    )

    affected_figure = px.bar(
        affected_dataframe,
        x="Affected Individuals",
        y="Barangay",
        orientation="h",
        text="Affected Individuals",
        title=(
            "Top barangays by latest reported "
            "affected individuals"
        ),
    )

    affected_figure.update_layout(
        xaxis_title="Affected individuals",
        yaxis_title="Barangay",
    )

    st.plotly_chart(
        affected_figure,
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


st.divider()


# ---------------------------------------------------------
# EVACUATION-CENTER SUMMARY
# ---------------------------------------------------------

st.subheader("Evacuation Center Summary")

evacuation_columns = st.columns(4)

with evacuation_columns[0]:
    st.metric(
        "Open Centers",
        int(evacuation_summary["open_centers"]),
    )

with evacuation_columns[1]:
    st.metric(
        "Registered Families",
        f"{int(evacuation_summary['families']):,}",
    )

with evacuation_columns[2]:
    st.metric(
        "Registered Individuals",
        f"{int(evacuation_summary['individuals']):,}",
    )

with evacuation_columns[3]:
    st.metric(
        "Critical Water Supply",
        int(evacuation_summary["critical_water"]),
    )


evacuation_condition_columns = st.columns(4)

with evacuation_condition_columns[0]:
    st.metric(
        "Critical Food Supply",
        int(evacuation_summary["critical_food"]),
    )

with evacuation_condition_columns[1]:
    st.metric(
        "No Electricity",
        int(
            evacuation_summary[
                "unavailable_electricity"
            ]
        ),
    )

with evacuation_condition_columns[2]:
    st.metric(
        "Medical Cases",
        int(evacuation_summary["medical_cases"]),
    )

with evacuation_condition_columns[3]:
    st.metric(
        "Reports Included",
        int(evacuation_summary["reports_included"]),
    )


st.write(
    "**Latest evacuation-center report timestamp:**",
    format_datetime(
        evacuation_summary["latest_update"]
    ),
)


st.divider()


# ---------------------------------------------------------
# EVACUATION-CENTER OCCUPANCY CHART
# ---------------------------------------------------------

st.subheader("Current Occupants by Evacuation Center")

evacuation_chart_rows = [
    {
        "Evacuation Center": record["center_name"],
        "Individuals": int(record["individuals"]),
    }
    for record in included_evacuation_rows
    if int(record["individuals"]) > 0
]

if not evacuation_chart_rows:
    st.info(
        "No evacuation-center occupants are currently "
        "reported in this dashboard mode."
    )

else:
    evacuation_dataframe = (
        pd.DataFrame(evacuation_chart_rows)
        .sort_values(
            "Individuals",
            ascending=True,
        )
    )

    evacuation_figure = px.bar(
        evacuation_dataframe,
        x="Individuals",
        y="Evacuation Center",
        orientation="h",
        text="Individuals",
        title=(
            "Latest reported individuals "
            "by evacuation center"
        ),
    )

    evacuation_figure.update_layout(
        xaxis_title="Individuals",
        yaxis_title="Evacuation center",
    )

    st.plotly_chart(
        evacuation_figure,
        use_container_width=True,
    )


st.divider()


# ---------------------------------------------------------
# BARANGAY / EVACUATION-CENTER RECONCILIATION
# ---------------------------------------------------------

st.subheader("Evacuation Data Reconciliation")

barangay_inside_ec = int(
    summary["inside_ec_individuals"]
)

center_registered = int(
    evacuation_summary["individuals"]
)

difference = (
    center_registered
    - barangay_inside_ec
)

reconciliation_columns = st.columns(3)

with reconciliation_columns[0]:
    st.metric(
        "Barangay-Reported Inside EC",
        f"{barangay_inside_ec:,}",
    )

with reconciliation_columns[1]:
    st.metric(
        "Center-Registered Individuals",
        f"{center_registered:,}",
    )

with reconciliation_columns[2]:
    st.metric(
        "Difference",
        f"{difference:+,}",
    )


if difference != 0:
    st.info(
        "A difference does not automatically indicate an "
        "error. Reporting times and responsible offices may "
        "differ. Reconcile the figures before official "
        "publication."
    )
else:
    st.success(
        "The current barangay and evacuation-center totals "
        "match in this dashboard mode."
    )
