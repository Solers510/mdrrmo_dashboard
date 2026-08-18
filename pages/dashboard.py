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
from utils.ui import (
    render_attention_required,
    render_dashboard_mode_status,
    render_dashboard_section_header,
    render_kpi_grid,
    render_operational_event_strip,
    render_operational_page_header,
)


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


def _counted_label(
    count: int,
    singular: str,
    plural: str | None = None,
) -> str:
    if count == 1:
        return singular

    return (
        plural
        if plural is not None
        else f"{singular}s"
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
        return (
            "1 minute ago"
            if minutes == 1
            else f"{minutes} minutes ago"
        )

    hours = minutes // 60

    if hours < 24:
        return (
            "1 hour ago"
            if hours == 1
            else f"{hours} hours ago"
        )

    days = hours // 24

    return (
        "1 day ago"
        if days == 1
        else f"{days} days ago"
    )


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


def format_road_status(
    value: object,
) -> str:
    """
    Shorten known verbose road-status labels only in the routine dashboard
    table. Full source wording remains available in the source-fields
    expander.
    """
    text = str(
        value
    )

    compact_labels = {
        "Passable to Large Vehicles Only": "Large vehicles only",
        "Passable to Small Vehicles Only": "Small vehicles only",
        "Passable to Light Vehicles Only": "Light vehicles only",
        "Passable with Difficulty": "Passable w/ difficulty",
        "Passable with Caution": "Passable w/ caution",
    }

    return compact_labels.get(
        text,
        text,
    )


def build_barangay_operational_table(
    rows: list[dict[str, object]],
) -> pd.DataFrame:
    table_rows = []

    for row in rows:
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

        table_rows.append(
            {
                "Barangay": (
                    row[
                        "barangay_name"
                    ]
                ),
                "Situation": (
                    row[
                        "situation_status"
                    ]
                ),
                "Affected (ind.)": int(
                    row[
                        "affected_individuals"
                    ]
                ),
                "Displaced (ind.)": (
                    inside
                    + outside
                ),
                "Road": format_road_status(
                    row[
                        "road_status"
                    ]
                ),
                "Power / Water": (
                    str(
                        row[
                            "power_status"
                        ]
                    )
                    + " / "
                    + str(
                        row[
                            "water_status"
                        ]
                    )
                ),
                "Rescue": int(
                    row[
                        "rescue_requests"
                    ]
                ),
                "Validation": (
                    row[
                        "validation_status"
                    ]
                ),
                "Report Age": (
                    format_table_age(
                        row[
                            "recorded_at"
                        ]
                    )
                ),
            }
        )

    return pd.DataFrame(
        table_rows
    )


def build_evacuation_operational_table(
    rows: list[dict[str, object]],
) -> pd.DataFrame:
    table_rows = []

    for row in rows:
        individuals = int(
            row[
                "individuals"
            ]
        )
        safe_capacity = int(
            row.get(
                "safe_capacity"
            )
            or 0
        )
        utilization = (
            (
                individuals
                / safe_capacity
            )
            * 100
            if safe_capacity > 0
            else None
        )

        occupancy = (
            (
                f"{individuals:,} / {safe_capacity:,}"
                f" · {utilization:.1f}%"
            )
            if utilization is not None
            else f"{individuals:,} / —"
        )

        table_rows.append(
            {
                "Evacuation Center": (
                    row[
                        "center_name"
                    ]
                ),
                "Status": (
                    row[
                        "status"
                    ]
                ),
                "Occupancy / Use": occupancy,
                "Food / Water": (
                    str(
                        row[
                            "food_status"
                        ]
                    )
                    + " / "
                    + str(
                        row[
                            "water_status"
                        ]
                    )
                ),
                "Power": (
                    row[
                        "electricity_status"
                    ]
                ),
                "Medical": int(
                    row[
                        "medical_cases"
                    ]
                ),
                "Validation": (
                    row[
                        "validation_status"
                    ]
                ),
                "Report Age": (
                    format_table_age(
                        row[
                            "recorded_at"
                        ]
                    )
                ),
            }
        )

    return pd.DataFrame(
        table_rows
    )


def format_table_age(
    value: datetime | None,
) -> str:
    """Compact age label for dense routine operational tables."""
    if value is None:
        return "—"

    current = datetime.now(
        MANILA_TIMEZONE
    )
    localized = value.astimezone(
        MANILA_TIMEZONE
    )
    seconds = max(
        int(
            (
                current
                - localized
            ).total_seconds()
        ),
        0,
    )

    if seconds < 60:
        return "<1m"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"

    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"

    days = hours // 24
    return f"{days}d"


def format_optional_count(
    value: object,
) -> str:
    if value is None:
        return "—"

    return f"{int(value):,}"

def build_reconciliation_operational_table(
    rows: list[dict[str, object]],
) -> pd.DataFrame:
    table_rows = []

    for row in rows:
        table_rows.append(
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
                "Families — Barangay / EC": (
                    format_optional_count(row["barangay_inside_families"])
                    + " / "
                    + format_optional_count(row["ec_inside_families"])
                ),
                "Individuals — Barangay / EC": (
                    format_optional_count(row["barangay_inside_individuals"])
                    + " / "
                    + format_optional_count(row["ec_inside_individuals"])
                ),
                "Barangay Age": (
                    format_age(
                        row[
                            "barangay_recorded_at"
                        ]
                    )
                ),
                "EC Source Age": (
                    format_age(
                        row[
                            "latest_ec_recorded_at"
                        ]
                    )
                ),
            }
        )

    return pd.DataFrame(
        table_rows
    )


def style_operational_chart(
    figure,
    *,
    height: int = 330,
) -> None:
    figure.update_layout(
        height=height,
        margin=dict(
            l=20,
            r=20,
            t=24,
            b=30,
        ),
        paper_bgcolor=(
            "rgba(0,0,0,0)"
        ),
        plot_bgcolor=(
            "rgba(0,0,0,0)"
        ),
        font=dict(
            color="#1A2540",
            size=12,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        hoverlabel=dict(
            namelength=-1,
        ),
    )

    figure.update_xaxes(
        gridcolor="#E5EAF2",
        zeroline=False,
        showline=False,
    )
    figure.update_yaxes(
        gridcolor="#E5EAF2",
        zeroline=False,
        showline=False,
    )


PLOTLY_DASHBOARD_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "displaylogo": False,
}

render_operational_page_header(
    title="Situation Dashboard",
    subtitle=(
        "Current operational picture for the active disaster event."
    ),
)

refresh_column, mode_column = st.columns(
    [1, 4],
    vertical_alignment="bottom",
)

with refresh_column:
    if st.button(
        "Refresh data",
        icon=":material/refresh:",
        width="stretch",
    ):
        st.rerun()

with mode_column:
    view_mode = st.radio(
        "Data mode",
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


sitrep_value = (
    active_event.get(
        "current_sitrep_number"
    )
)
sitrep_text = (
    str(sitrep_value)
    if sitrep_value not in {
        None,
        "",
    }
    else "Not set"
)

reference = active_event.get(
    "official_reference"
)
overview = active_event.get(
    "situation_overview"
)

render_operational_event_strip(
    event_name=event_display_name(
        active_event
    ),
    hazard_type=str(
        active_event["hazard_type"]
    ),
    alert_code=str(
        active_event["alert_code"]
    ),
    eoc_status=str(
        active_event["eoc_status"]
    ),
    sitrep=sitrep_text,
    official_reference=(
        str(reference)
        if reference
        else None
    ),
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

render_dashboard_mode_status(
    mode=view_mode
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


reconciliation_summary = dashboard[
    "reconciliation_summary"
]

reconciliation_issue_count = (
    int(
        reconciliation_summary[
            "mismatch"
        ]
    )
    + int(
        reconciliation_summary[
            "missing_source"
        ]
    )
    + int(
        reconciliation_summary[
            "allocation_conflict"
        ]
    )
)

pending_rescue_count = int(
    summary[
        "pending_rescue_requests"
    ]
)
impassable_road_count = int(
    summary[
        "impassable_roads"
    ]
)
power_interruption_count = int(
    summary[
        "interrupted_power"
    ]
)
water_interruption_count = int(
    summary[
        "interrupted_water"
    ]
)
over_capacity_center_count = int(
    evacuation_summary[
        "over_capacity_centers"
    ]
)
medical_case_count = int(
    evacuation_summary[
        "medical_cases"
    ]
)
population_consistency_count = int(
    summary[
        "population_consistency_issues"
    ]
)

attention_specs = (
    (
        _counted_label(
            pending_rescue_count,
            "Pending Rescue Request",
        ),
        pending_rescue_count,
        "danger",
    ),
    (
        _counted_label(
            impassable_road_count,
            "Impassable Road",
        ),
        impassable_road_count,
        "danger",
    ),
    (
        _counted_label(
            power_interruption_count,
            "Power Interruption",
        ),
        power_interruption_count,
        "warning",
    ),
    (
        _counted_label(
            water_interruption_count,
            "Water Interruption",
        ),
        water_interruption_count,
        "warning",
    ),
    (
        _counted_label(
            over_capacity_center_count,
            "Over-Capacity Center",
        ),
        over_capacity_center_count,
        "danger",
    ),
    (
        "Critical Food",
        int(
            evacuation_summary[
                "critical_food"
            ]
        ),
        "danger",
    ),
    (
        "Critical Water",
        int(
            evacuation_summary[
                "critical_water"
            ]
        ),
        "danger",
    ),
    (
        _counted_label(
            medical_case_count,
            "Medical Case",
        ),
        medical_case_count,
        "warning",
    ),
    (
        "Pending Validation",
        int(
            summary[
                "pending_validation"
            ]
        ),
        "warning",
    ),
    (
        "Needs Correction",
        int(
            summary[
                "needs_correction"
            ]
        ),
        "danger",
    ),
    (
        _counted_label(
            population_consistency_count,
            "Population Consistency Issue",
        ),
        population_consistency_count,
        "danger",
    ),
    (
        _counted_label(
            reconciliation_issue_count,
            "Reconciliation Issue",
        ),
        reconciliation_issue_count,
        "warning",
    ),
)

attention_items = [
    {
        "label": label,
        "value": value,
        "tone": tone,
    }
    for label, value, tone in attention_specs
    if value > 0
]

if not dashboard[
    "reconciliation_available"
]:
    attention_items.append(
        {
            "label": "Population Reconciliation",
            "value": "Unavailable",
            "tone": "warning",
        }
    )

render_dashboard_section_header(
    title="Attention Required",
    subtitle=(
        "Current non-zero exceptions that may require operational "
        "review or follow-up."
    ),
)

render_attention_required(
    attention_items
)

render_dashboard_section_header(
    title="Situation Summary",
    subtitle=(
        "Primary population and evacuation indicators for the selected "
        "data mode."
    ),
)

render_kpi_grid(
    [
        {
            "label": "Affected Barangays",
            "value": f"{int(summary['affected_barangays']):,}",
        },
        {
            "label": "Affected Families",
            "value": f"{int(summary['affected_families']):,}",
        },
        {
            "label": "Affected Individuals",
            "value": f"{int(summary['affected_individuals']):,}",
        },
        {
            "label": "Displaced Individuals",
            "value": f"{int(summary['displaced_individuals']):,}",
        },
        {
            "label": "Operational ECs",
            "value": f"{int(evacuation_summary['open_centers']):,}",
        },
    ]
)

render_dashboard_section_header(
    title="Population Breakdown",
    subtitle=(
        "Location of affected people: non-displaced in their homes, "
        "displaced inside evacuation centers, or displaced outside centers."
    ),
)

render_kpi_grid(
    [
        {
            "label": "Non-Displaced — Families",
            "value": (
                f"{int(summary['affected_not_displaced_families']):,}"
            ),
        },
        {
            "label": "Non-Displaced — Individuals",
            "value": (
                f"{int(summary['affected_not_displaced_individuals']):,}"
            ),
        },
    ],
    compact=False,
)

render_dashboard_section_header(
    title="Displaced Population",
    subtitle=(
        "Location of affected people who have left their homes."
    ),
)

render_kpi_grid(
    [
        {
            "label": "Inside EC — Families",
            "value": f"{int(summary['inside_ec_families']):,}",
        },
        {
            "label": "Outside EC — Families",
            "value": f"{int(summary['outside_ec_families']):,}",
        },
        {
            "label": "Inside EC — Individuals",
            "value": f"{int(summary['inside_ec_individuals']):,}",
        },
        {
            "label": "Outside EC — Individuals",
            "value": f"{int(summary['outside_ec_individuals']):,}",
        },
    ],
    compact=True,
)

render_dashboard_section_header(
    title="Reporting & Freshness",
    subtitle=(
        "Coverage, validation workload, and age of the current source "
        "reports."
    ),
)

render_kpi_grid(
    [
        {
            "label": "Barangays Reporting",
            "value": (
                f"{int(summary['reports_received'])}"
                f" / "
                f"{int(summary['total_barangays'])}"
            ),
            "meta": (
                f"{float(summary['coverage_percent']):.1f}% coverage"
            ),
        },
        {
            "label": "Pending Validation",
            "value": f"{int(summary['pending_validation']):,}",
        },
        {
            "label": "Needs Correction",
            "value": f"{int(summary['needs_correction']):,}",
        },
        {
            "label": "Newest Barangay Report",
            "value": format_age(
                summary[
                    "latest_update"
                ]
            ),
            "meta": format_datetime(
                summary[
                    "latest_update"
                ]
            ),
        },
        {
            "label": "Oldest Current Report",
            "value": format_age(
                summary[
                    "oldest_current_update"
                ]
            ),
            "meta": format_datetime(
                summary[
                    "oldest_current_update"
                ]
            ),
        },
        {
            "label": "Newest EC Report",
            "value": format_age(
                evacuation_summary[
                    "latest_update"
                ]
            ),
            "meta": format_datetime(
                evacuation_summary[
                    "latest_update"
                ]
            ),
        },
    ],
    compact=True,
)

st.divider()

barangay_tab, evacuation_tab, quality_tab = st.tabs(
    (
        f"Barangays ({len(selected_rows)})",
        f"Evacuation Centers ({len(evacuation_rows)})",
        (
            "Data Quality "
            f"({reconciliation_issue_count})"
        ),
    )
)


with barangay_tab:
    render_dashboard_section_header(
        title="Barangay Operational Picture",
        subtitle=(
            "Routine view prioritizing current population impact, "
            "access, utilities, rescue demand, validation, and freshness."
        ),
    )

    if not selected_rows:
        st.info(
            "No barangay reports are available "
            "in this dashboard mode."
        )
    else:
        operational_table = (
            build_barangay_operational_table(
                selected_rows
            )
        )

        st.dataframe(
            operational_table,
            width="stretch",
            hide_index=True,
            column_order=(
                "Barangay",
                "Situation",
                "Affected (ind.)",
                "Displaced (ind.)",
                "Road",
                "Power / Water",
                "Rescue",
                "Validation",
                "Report Age",
            ),
            column_config={
                "Barangay": (
                    st.column_config.TextColumn(
                        "Barangay",
                        width=150,
                        pinned=True,
                    )
                ),
                "Situation": (
                    st.column_config.TextColumn(
                        "Situation",
                        width=95,
                    )
                ),
                "Affected (ind.)": (
                    st.column_config.NumberColumn(
                        "Affected",
                        help="Affected individuals",
                        width=78,
                        format="%d",
                    )
                ),
                "Displaced (ind.)": (
                    st.column_config.NumberColumn(
                        "Displaced",
                        help=(
                            "Individuals recorded inside "
                            "or outside evacuation centers"
                        ),
                        width=82,
                        format="%d",
                    )
                ),
                "Road": (
                    st.column_config.TextColumn(
                        "Road",
                        width=175,
                    )
                ),
                "Power / Water": (
                    st.column_config.TextColumn(
                        "Power / Water",
                        width=130,
                    )
                ),
                "Rescue": (
                    st.column_config.NumberColumn(
                        "Rescue",
                        width=70,
                        format="%d",
                    )
                ),
                "Validation": (
                    st.column_config.TextColumn(
                        "Validation",
                        width=100,
                    )
                ),
                "Report Age": (
                    st.column_config.TextColumn(
                        "Age",
                        help="Age since the current report was recorded",
                        width=60,
                    )
                ),
            },
        )

        with st.expander(
            "Full barangay source fields",
            expanded=False,
        ):
            st.caption(
                "Includes family counts, inside/outside EC split, "
                "individual utility fields, timestamps, and validation data."
            )

            st.dataframe(
                build_barangay_table(
                    selected_rows
                ),
                width="stretch",
                hide_index=True,
            )

    affected_chart_rows = [
        {
            "Barangay": (
                row[
                    "barangay_name"
                ]
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

        if (
            inside > 0
            or outside > 0
        ):
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

    if (
        affected_chart_rows
        or displacement_rows
    ):
        with st.expander(
            "Analytical views",
            expanded=False,
        ):
            if affected_chart_rows:
                st.markdown(
                    "**Most affected barangays**"
                )

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
                )

                affected_figure.update_traces(
                    textposition="inside",
                    cliponaxis=False,
                )
                affected_figure.update_layout(
                    showlegend=False,
                )
                affected_figure.update_xaxes(
                    title="Affected individuals",
                )
                affected_figure.update_yaxes(
                    title="",
                )

                style_operational_chart(
                    affected_figure
                )

                st.plotly_chart(
                    affected_figure,
                    width="stretch",
                    config=(
                        PLOTLY_DASHBOARD_CONFIG
                    ),
                )

            if displacement_rows:
                st.markdown(
                    "**Displacement location by barangay**"
                )

                displacement_figure = px.bar(
                    pd.DataFrame(
                        displacement_rows
                    ),
                    x="Barangay",
                    y="Individuals",
                    color="Location",
                    barmode="stack",
                )

                displacement_figure.update_xaxes(
                    title="",
                )
                displacement_figure.update_yaxes(
                    title="Individuals",
                )

                style_operational_chart(
                    displacement_figure
                )

                st.plotly_chart(
                    displacement_figure,
                    width="stretch",
                    config=(
                        PLOTLY_DASHBOARD_CONFIG
                    ),
                )


with evacuation_tab:
    render_dashboard_section_header(
        title="Evacuation Center Operations",
        subtitle=(
            "Current center status, occupancy, capacity, supplies, "
            "medical demand, validation, and report freshness."
        ),
    )

    render_kpi_grid(
        [
            {
                "label": "Operational Centers",
                "value": (
                    f"{int(evacuation_summary['open_centers']):,}"
                ),
            },
            {
                "label": "Registered Families",
                "value": (
                    f"{int(evacuation_summary['families']):,}"
                ),
            },
            {
                "label": "Registered Individuals",
                "value": (
                    f"{int(evacuation_summary['individuals']):,}"
                ),
            },
            {
                "label": "Overall Capacity Use",
                "value": (
                    (
                        f"{float(evacuation_summary['capacity_utilization_percent']):.1f}%"
                    )
                    if int(
                        evacuation_summary[
                            "safe_capacity"
                        ]
                    ) > 0
                    else "No data"
                ),
            },
        ],
    )

    if not evacuation_rows:
        st.info(
            "No evacuation-center reports are available "
            "in this dashboard mode."
        )
    else:
        st.dataframe(
            build_evacuation_operational_table(
                evacuation_rows
            ),
            width="stretch",
            hide_index=True,
            column_order=(
                "Evacuation Center",
                "Status",
                "Occupancy / Use",
                "Food / Water",
                "Power",
                "Medical",
                "Validation",
                "Report Age",
            ),
            column_config={
                "Evacuation Center": (
                    st.column_config.TextColumn(
                        "Evacuation Center",
                        width=240,
                        pinned=True,
                    )
                ),
                "Status": (
                    st.column_config.TextColumn(
                        "Status",
                        width=90,
                    )
                ),
                "Occupancy / Use": (
                    st.column_config.TextColumn(
                        "Occupancy / Use",
                        help=(
                            "Individuals / safe capacity · utilization"
                        ),
                        width=125,
                    )
                ),
                "Food / Water": (
                    st.column_config.TextColumn(
                        "Food / Water",
                        width=130,
                    )
                ),
                "Power": (
                    st.column_config.TextColumn(
                        "Power",
                        width=85,
                    )
                ),
                "Medical": (
                    st.column_config.NumberColumn(
                        "Medical",
                        width=65,
                        format="%d",
                    )
                ),
                "Validation": (
                    st.column_config.TextColumn(
                        "Validation",
                        width=95,
                    )
                ),
                "Report Age": (
                    st.column_config.TextColumn(
                        "Age",
                        help="Age since the current report was recorded",
                        width=60,
                    )
                ),
            },
        )

        with st.expander(
            "Full evacuation-center source fields",
            expanded=False,
        ):
            st.caption(
                "Includes families, exact safe capacity, individual "
                "supply fields, electricity, medical cases, timestamps, "
                "and validation data."
            )

            st.dataframe(
                build_evacuation_table(
                    evacuation_rows
                ),
                width="stretch",
                hide_index=True,
            )

    capacity_chart_rows = []

    for row in included_evacuation_rows:
        individuals = int(
            row[
                "individuals"
            ]
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
                        "Measure": (
                            "Occupants"
                        ),
                        "Individuals": (
                            individuals
                        ),
                    },
                    {
                        "Evacuation Center": (
                            row[
                                "center_name"
                            ]
                        ),
                        "Measure": (
                            "Safe Capacity"
                        ),
                        "Individuals": (
                            safe_capacity
                        ),
                    },
                )
            )

    if capacity_chart_rows:
        with st.expander(
            "Capacity analytical view",
            expanded=False,
        ):
            capacity_figure = px.bar(
                pd.DataFrame(
                    capacity_chart_rows
                ),
                x="Evacuation Center",
                y="Individuals",
                color="Measure",
                barmode="group",
            )

            capacity_figure.update_xaxes(
                title="",
            )
            capacity_figure.update_yaxes(
                title="Individuals",
            )

            style_operational_chart(
                capacity_figure
            )

            st.plotly_chart(
                capacity_figure,
                width="stretch",
                config=(
                    PLOTLY_DASHBOARD_CONFIG
                ),
            )


with quality_tab:
    render_dashboard_section_header(
        title="Source Reconciliation",
        subtitle=(
            "Compare barangay inside-EC figures with evacuation-center "
            "attribution. Differences are review signals, not automatic "
            "proof that a source is wrong."
        ),
    )

    render_kpi_grid(
        [
            {
                "label": "Matches",
                "value": (
                    f"{int(reconciliation_summary['match']):,}"
                ),
            },
            {
                "label": "Mismatches",
                "value": (
                    f"{int(reconciliation_summary['mismatch']):,}"
                ),
            },
            {
                "label": "Missing Source",
                "value": (
                    f"{int(reconciliation_summary['missing_source']):,}"
                ),
            },
            {
                "label": "Allocation Conflicts",
                "value": (
                    f"{int(reconciliation_summary['allocation_conflict']):,}"
                ),
            },
        ],
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
            issue_label = _counted_label(
                len(
                    problem_rows
                ),
                "barangay currently requires",
                "barangays currently require",
            )

            st.warning(
                f"{len(problem_rows)} {issue_label} "
                "source or population reconciliation."
            )

            st.dataframe(
                build_reconciliation_operational_table(
                    problem_rows
                ),
                width="stretch",
                hide_index=True,
                column_order=(
                    "Barangay",
                    "Status",
                    "Families — Barangay / EC",
                    "Individuals — Barangay / EC",
                    "Barangay Age",
                    "EC Source Age",
                ),
                column_config={
                    "Barangay": (
                        st.column_config.TextColumn(
                            "Barangay",
                            width=150,
                            pinned=True,
                        )
                    ),
                    "Status": (
                        st.column_config.TextColumn(
                            "Status",
                            width=145,
                        )
                    ),
                    "Families — Barangay / EC": (
                        st.column_config.TextColumn(
                            "Families B / EC",
                            help=(
                                "Barangay inside-EC families "
                                "/ EC-attributed families"
                            ),
                            width=125,
                        )
                    ),
                    "Individuals — Barangay / EC": (
                        st.column_config.TextColumn(
                            "Individuals B / EC",
                            help=(
                                "Barangay inside-EC individuals "
                                "/ EC-attributed individuals"
                            ),
                            width=135,
                        )
                    ),
                    "Barangay Age": (
                        st.column_config.TextColumn(
                            "Barangay Age",
                            width=110,
                        )
                    ),
                    "EC Source Age": (
                        st.column_config.TextColumn(
                            "EC Source Age",
                            width=110,
                        )
                    ),
                },
            )

            with st.expander(
                "Full reconciliation source timestamps",
                expanded=False,
            ):
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
                    width="stretch",
                    hide_index=True,
                )

    st.caption(
        "Before correcting or publishing official figures, compare "
        "timestamps and source documents. Reconciliation remains a "
        "warning workflow and does not rewrite operational reports."
    )
