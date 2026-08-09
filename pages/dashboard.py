from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st

from config.access_control import (
    PERMISSION_VIEW_DASHBOARD,
)
from services.dashboard_service import (
    DashboardDataIntegrityError,
    DashboardServiceError,
    get_dashboard_bundle,
)
from utils.auth import require_permission


current_user = require_permission(
    PERMISSION_VIEW_DASHBOARD
)

MANILA_TIMEZONE = ZoneInfo(
    "Asia/Manila"
)

PROVISIONAL_INCLUDED_STATUSES = {
    "Submitted",
    "For Validation",
    "Validated",
}


def format_datetime(
    value: datetime | None,
) -> str:
    if value is None:
        return "No report recorded"

    return value.astimezone(
        MANILA_TIMEZONE
    ).strftime(
        "%d %b %Y, %I:%M %p"
    )


def format_age(
    value: datetime | None,
) -> str:
    if value is None:
        return "No report"

    current = datetime.now(
        MANILA_TIMEZONE
    )
    localized = value.astimezone(
        MANILA_TIMEZONE
    )
    delta = current - localized

    seconds = max(
        int(delta.total_seconds()),
        0,
    )

    if seconds < 60:
        return "Just now"

    minutes = seconds // 60

    if minutes < 60:
        return f"{minutes} min ago"

    hours = minutes // 60

    if hours < 24:
        return f"{hours} hr ago"

    days = hours // 24
    return f"{days} day(s) ago"


def record_is_included(
    record: dict[str, object],
    *,
    view_mode: str,
) -> bool:
    validation_status = str(
        record["validation_status"]
    )

    if view_mode == "Official Validated":
        return (
            validation_status
            == "Validated"
        )

    return (
        validation_status
        in PROVISIONAL_INCLUDED_STATUSES
    )


def event_display_name(
    active_event: dict[str, object],
) -> str:
    event_name = str(
        active_event["event_name"]
    )
    classification = (
        active_event.get(
            "classification"
        )
    )

    if (
        classification is not None
        and str(classification).strip()
    ):
        return (
            f"{classification} "
            f"{event_name}"
        )

    return event_name


def build_barangay_table(
    rows: list[dict[str, object]],
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Barangay": row["barangay_name"],
                "Situation": row["situation_status"],
                "Affected Families": (
                    row["affected_families"]
                ),
                "Affected Individuals": (
                    row["affected_individuals"]
                ),
                "Inside EC": (
                    row["inside_ec_individuals"]
                ),
                "Outside EC": (
                    row["outside_ec_individuals"]
                ),
                "Road": row["road_status"],
                "Power": row["power_status"],
                "Water": row["water_status"],
                "Rescue": row["rescue_requests"],
                "Validation": (
                    row["validation_status"]
                ),
                "Report Age": (
                    format_age(
                        row["recorded_at"]
                    )
                ),
                "Recorded At": (
                    row["recorded_at"]
                ),
            }
            for row in rows
        ]
    )


def build_evacuation_table(
    rows: list[dict[str, object]],
) -> pd.DataFrame:
    table_rows = []

    for row in rows:
        individuals = int(
            row["individuals"]
        )
        safe_capacity = int(
            row.get("safe_capacity")
            or 0
        )

        utilization = (
            (individuals / safe_capacity)
            * 100
            if safe_capacity > 0
            else None
        )

        table_rows.append(
            {
                "Evacuation Center": (
                    row["center_name"]
                ),
                "Status": row["status"],
                "Families": row["families"],
                "Individuals": individuals,
                "Safe Capacity": safe_capacity,
                "Utilization %": (
                    round(utilization, 1)
                    if utilization is not None
                    else None
                ),
                "Food": row["food_status"],
                "Water": row["water_status"],
                "Electricity": (
                    row["electricity_status"]
                ),
                "Medical Cases": (
                    row["medical_cases"]
                ),
                "Validation": (
                    row["validation_status"]
                ),
                "Report Age": (
                    format_age(
                        row["recorded_at"]
                    )
                ),
                "Recorded At": (
                    row["recorded_at"]
                ),
            }
        )

    return pd.DataFrame(
        table_rows
    )


st.title(
    "MDRRMO Naic Situation Dashboard"
)
st.caption(
    "Current operational picture for the active disaster event."
)

refresh_column, mode_column = st.columns(
    [1, 4]
)

with refresh_column:
    if st.button(
        "Refresh",
        use_container_width=True,
    ):
        st.rerun()

with mode_column:
    view_mode = st.radio(
        "Dashboard data mode",
        options=(
            "Provisional Operational",
            "Official Validated",
        ),
        horizontal=True,
        help=(
            "Provisional uses the latest submitted operational "
            "reports. Official uses the latest report that has "
            "completed validation."
        ),
    )

try:
    dashboard = get_dashboard_bundle()

except DashboardDataIntegrityError as error:
    st.error(str(error))
    st.stop()

except DashboardServiceError as error:
    st.error(str(error))
    st.stop()

except Exception:
    st.error(
        "The dashboard could not be loaded. "
        "Contact the system administrator if the problem continues."
    )
    st.stop()


active_event = dashboard[
    "active_event"
]

if active_event is None:
    st.warning(
        "No active disaster event exists. "
        "Create an event through Event Control first."
    )
    st.stop()


event_columns = st.columns(4)

event_columns[0].metric(
    "Active Event",
    event_display_name(
        active_event
    ),
)

event_columns[1].metric(
    "Alert Level",
    str(
        active_event["alert_code"]
    ),
)

event_columns[2].metric(
    "EOC Status",
    str(
        active_event["eoc_status"]
    ),
)

sitrep_value = (
    active_event.get(
        "current_sitrep_number"
    )
)

event_columns[3].metric(
    "Current SitRep",
    (
        str(sitrep_value)
        if sitrep_value not in {
            None,
            "",
        }
        else "Not set"
    ),
)

reference = active_event.get(
    "official_reference"
)
overview = active_event.get(
    "situation_overview"
)

if reference:
    st.caption(
        f"Official reference: {reference}"
    )

if overview:
    with st.expander(
        "Current situation overview",
        expanded=False,
    ):
        st.write(
            overview
        )


if view_mode == "Provisional Operational":
    summary = dashboard[
        "provisional_summary"
    ]
    selected_rows = dashboard[
        "provisional_rows"
    ]
    evacuation_summary = dashboard[
        "provisional_evacuation_summary"
    ]
    evacuation_rows = dashboard[
        "provisional_evacuation_rows"
    ]

    st.warning(
        "Operational view: some figures may still be awaiting "
        "formal validation."
    )

else:
    summary = dashboard[
        "official_summary"
    ]
    selected_rows = dashboard[
        "official_rows"
    ]
    evacuation_summary = dashboard[
        "official_evacuation_summary"
    ]
    evacuation_rows = dashboard[
        "official_evacuation_rows"
    ]

    st.success(
        "Official view: figures are based only on validated reports."
    )


if summary is None or evacuation_summary is None:
    st.info(
        "No dashboard summary is available for this event."
    )
    st.stop()


included_barangay_rows = [
    row
    for row in selected_rows
    if record_is_included(
        row,
        view_mode=view_mode,
    )
]

included_evacuation_rows = [
    row
    for row in evacuation_rows
    if record_is_included(
        row,
        view_mode=view_mode,
    )
]


st.divider()

st.subheader(
    "Affected Population"
)

affected_columns = st.columns(3)

affected_columns[0].metric(
    "Affected Barangays",
    int(
        summary[
            "affected_barangays"
        ]
    ),
)

affected_columns[1].metric(
    "Affected Families",
    f"{int(summary['affected_families']):,}",
)

affected_columns[2].metric(
    "Affected Individuals",
    f"{int(summary['affected_individuals']):,}",
)


st.markdown(
    "### Inside Evacuation Centers"
)

inside_columns = st.columns(3)

inside_columns[0].metric(
    "Families",
    f"{int(summary['inside_ec_families']):,}",
)

inside_columns[1].metric(
    "Individuals",
    f"{int(summary['inside_ec_individuals']):,}",
)

inside_columns[2].metric(
    "Operational Centers",
    int(
        evacuation_summary[
            "open_centers"
        ]
    ),
)


st.markdown(
    "### Outside Evacuation Centers"
)

outside_columns = st.columns(2)

outside_columns[0].metric(
    "Families",
    f"{int(summary['outside_ec_families']):,}",
)

outside_columns[1].metric(
    "Individuals",
    f"{int(summary['outside_ec_individuals']):,}",
)


st.markdown(
    "### Displacement Reconciliation"
)

displacement_columns = st.columns(4)

displacement_columns[0].metric(
    "Total Displaced Families",
    f"{int(summary['displaced_families']):,}",
)

displacement_columns[1].metric(
    "Total Displaced Individuals",
    f"{int(summary['displaced_individuals']):,}",
)

displacement_columns[2].metric(
    "Affected, Not Displaced — Families",
    f"{int(summary['affected_not_displaced_families']):,}",
)

displacement_columns[3].metric(
    "Affected, Not Displaced — Individuals",
    f"{int(summary['affected_not_displaced_individuals']):,}",
)

if int(
    summary[
        "population_consistency_issues"
    ]
) > 0:
    st.error(
        "One or more current barangay reports contain "
        "population figures that require correction."
    )


st.divider()

st.subheader(
    "Immediate Operational Concerns"
)

concern_columns = st.columns(4)

concern_columns[0].metric(
    "Pending Rescue Requests",
    int(
        summary[
            "pending_rescue_requests"
        ]
    ),
)

concern_columns[1].metric(
    "Impassable Roads",
    int(
        summary[
            "impassable_roads"
        ]
    ),
)

concern_columns[2].metric(
    "Power Interruptions",
    int(
        summary[
            "interrupted_power"
        ]
    ),
)

concern_columns[3].metric(
    "Water Interruptions",
    int(
        summary[
            "interrupted_water"
        ]
    ),
)

ec_concern_columns = st.columns(4)

ec_concern_columns[0].metric(
    "Over-Capacity Centers",
    int(
        evacuation_summary[
            "over_capacity_centers"
        ]
    ),
)

ec_concern_columns[1].metric(
    "Critical Food",
    int(
        evacuation_summary[
            "critical_food"
        ]
    ),
)

ec_concern_columns[2].metric(
    "Critical Water",
    int(
        evacuation_summary[
            "critical_water"
        ]
    ),
)

ec_concern_columns[3].metric(
    "Medical Cases",
    int(
        evacuation_summary[
            "medical_cases"
        ]
    ),
)


barangay_tab, evacuation_tab, quality_tab = st.tabs(
    (
        "Barangay Situation",
        "Evacuation Centers",
        "Reporting & Data Quality",
    )
)


with barangay_tab:
    st.subheader(
        "Latest Barangay Situation"
    )

    if not selected_rows:
        st.info(
            "No barangay reports are available "
            "in this dashboard mode."
        )
    else:
        st.dataframe(
            build_barangay_table(
                selected_rows
            ),
            use_container_width=True,
            hide_index=True,
        )

    affected_chart_rows = [
        {
            "Barangay": (
                row["barangay_name"]
            ),
            "Affected Individuals": int(
                row[
                    "affected_individuals"
                ]
            ),
        }
        for row in included_barangay_rows
        if int(
            row[
                "affected_individuals"
            ]
        ) > 0
    ]

    if affected_chart_rows:
        affected_dataframe = (
            pd.DataFrame(
                affected_chart_rows
            )
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
                "Barangays with the Most "
                "Affected Individuals"
            ),
        )

        affected_figure.update_layout(
            xaxis_title=(
                "Affected individuals"
            ),
            yaxis_title="",
        )

        st.plotly_chart(
            affected_figure,
            use_container_width=True,
        )

    displacement_rows = []

    for row in included_barangay_rows:
        inside = int(
            row[
                "inside_ec_individuals"
            ]
        )
        outside = int(
            row[
                "outside_ec_individuals"
            ]
        )

        if inside > 0 or outside > 0:
            displacement_rows.extend(
                (
                    {
                        "Barangay": (
                            row[
                                "barangay_name"
                            ]
                        ),
                        "Location": (
                            "Inside EC"
                        ),
                        "Individuals": inside,
                    },
                    {
                        "Barangay": (
                            row[
                                "barangay_name"
                            ]
                        ),
                        "Location": (
                            "Outside EC"
                        ),
                        "Individuals": outside,
                    },
                )
            )

    if displacement_rows:
        displacement_figure = px.bar(
            pd.DataFrame(
                displacement_rows
            ),
            x="Barangay",
            y="Individuals",
            color="Location",
            barmode="stack",
            title=(
                "Displaced Individuals: "
                "Inside vs Outside Evacuation Centers"
            ),
        )

        displacement_figure.update_layout(
            xaxis_title="",
            yaxis_title="Individuals",
        )

        st.plotly_chart(
            displacement_figure,
            use_container_width=True,
        )


with evacuation_tab:
    st.subheader(
        "Evacuation Center Status"
    )

    capacity_columns = st.columns(4)

    capacity_columns[0].metric(
        "Operational Centers",
        int(
            evacuation_summary[
                "open_centers"
            ]
        ),
    )

    capacity_columns[1].metric(
        "Registered Families",
        f"{int(evacuation_summary['families']):,}",
    )

    capacity_columns[2].metric(
        "Registered Individuals",
        f"{int(evacuation_summary['individuals']):,}",
    )

    capacity_columns[3].metric(
        "Overall Capacity Use",
        (
            f"{float(evacuation_summary['capacity_utilization_percent']):.1f}%"
            if int(
                evacuation_summary[
                    "safe_capacity"
                ]
            ) > 0
            else "No capacity data"
        ),
    )

    if not evacuation_rows:
        st.info(
            "No evacuation-center reports are available "
            "in this dashboard mode."
        )
    else:
        st.dataframe(
            build_evacuation_table(
                evacuation_rows
            ),
            use_container_width=True,
            hide_index=True,
        )

    capacity_chart_rows = []

    for row in included_evacuation_rows:
        individuals = int(
            row["individuals"]
        )
        safe_capacity = int(
            row.get(
                "safe_capacity"
            )
            or 0
        )

        if (
            individuals > 0
            or safe_capacity > 0
        ):
            capacity_chart_rows.extend(
                (
                    {
                        "Evacuation Center": (
                            row[
                                "center_name"
                            ]
                        ),
                        "Measure": "Occupants",
                        "Individuals": individuals,
                    },
                    {
                        "Evacuation Center": (
                            row[
                                "center_name"
                            ]
                        ),
                        "Measure": "Safe Capacity",
                        "Individuals": safe_capacity,
                    },
                )
            )

    if capacity_chart_rows:
        capacity_figure = px.bar(
            pd.DataFrame(
                capacity_chart_rows
            ),
            x="Evacuation Center",
            y="Individuals",
            color="Measure",
            barmode="group",
            title=(
                "Evacuation Center Occupancy "
                "Compared with Safe Capacity"
            ),
        )

        capacity_figure.update_layout(
            xaxis_title="",
            yaxis_title="Individuals",
        )

        st.plotly_chart(
            capacity_figure,
            use_container_width=True,
        )


with quality_tab:
    st.subheader(
        "Reporting Coverage"
    )

    coverage_columns = st.columns(4)

    coverage_columns[0].metric(
        "Barangay Reports Received",
        (
            f"{int(summary['reports_received'])}"
            f" / "
            f"{int(summary['total_barangays'])}"
        ),
    )

    coverage_columns[1].metric(
        "Coverage",
        f"{float(summary['coverage_percent']):.1f}%",
    )

    coverage_columns[2].metric(
        "Pending Validation",
        int(
            summary[
                "pending_validation"
            ]
        ),
    )

    coverage_columns[3].metric(
        "Needs Correction",
        int(
            summary[
                "needs_correction"
            ]
        ),
    )

    st.write(
        "**Newest current barangay report:**",
        format_datetime(
            summary[
                "latest_update"
            ]
        ),
        f"({format_age(summary['latest_update'])})",
    )

    st.write(
        "**Oldest current barangay report:**",
        format_datetime(
            summary[
                "oldest_current_update"
            ]
        ),
        (
            f"({format_age(summary['oldest_current_update'])})"
        ),
    )

    st.write(
        "**Newest current evacuation-center report:**",
        format_datetime(
            evacuation_summary[
                "latest_update"
            ]
        ),
        (
            f"({format_age(evacuation_summary['latest_update'])})"
        ),
    )

    st.divider()

    st.subheader(
        "Barangay / Evacuation-Center Reconciliation"
    )

    reconciliation_summary = dashboard[
        "reconciliation_summary"
    ]

    reconciliation_columns = st.columns(4)

    reconciliation_columns[0].metric(
        "Matches",
        int(
            reconciliation_summary[
                "match"
            ]
        ),
    )

    reconciliation_columns[1].metric(
        "Mismatches",
        int(
            reconciliation_summary[
                "mismatch"
            ]
        ),
    )

    reconciliation_columns[2].metric(
        "Missing Source",
        int(
            reconciliation_summary[
                "missing_source"
            ]
        ),
    )

    reconciliation_columns[3].metric(
        "Allocation Conflicts",
        int(
            reconciliation_summary[
                "allocation_conflict"
            ]
        ),
    )

    if not dashboard[
        "reconciliation_available"
    ]:
        st.warning(
            "Population reconciliation could not be loaded. "
            "The main dashboard figures remain available."
        )
    else:
        problem_rows = [
            row
            for row in dashboard[
                "reconciliation_rows"
            ]
            if row[
                "reconciliation_status"
            ]
            in {
                "Mismatch",
                "No Barangay Report",
                "No EC Report",
                "Allocation Conflict",
            }
        ]

        if not problem_rows:
            st.success(
                "No current population reconciliation issue "
                "requires attention."
            )
        else:
            st.warning(
                f"{len(problem_rows)} barangay(s) currently require "
                "source or population reconciliation."
            )

            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Barangay": (
                                row[
                                    "barangay_name"
                                ]
                            ),
                            "Status": (
                                row[
                                    "reconciliation_status"
                                ]
                            ),
                            "Barangay Inside EC — Families": (
                                row[
                                    "barangay_inside_families"
                                ]
                            ),
                            "EC Attributed — Families": (
                                row[
                                    "ec_inside_families"
                                ]
                            ),
                            "Barangay Inside EC — Individuals": (
                                row[
                                    "barangay_inside_individuals"
                                ]
                            ),
                            "EC Attributed — Individuals": (
                                row[
                                    "ec_inside_individuals"
                                ]
                            ),
                            "Barangay Report": (
                                row[
                                    "barangay_recorded_at"
                                ]
                            ),
                            "Latest EC Source": (
                                row[
                                    "latest_ec_recorded_at"
                                ]
                            ),
                        }
                        for row in problem_rows
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

    st.caption(
        "Reconciliation differences are warnings, not automatic "
        "proof that a report is wrong. Compare timestamps and source "
        "documents before correcting or publishing official figures."
    )
