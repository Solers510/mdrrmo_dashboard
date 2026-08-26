import importlib
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Callable

import pandas as pd
import plotly.express as px
import streamlit as st
import services.dashboard_service as dashboard_service
import utils.ui as dashboard_ui

from config.access_control import PERMISSION_VIEW_DASHBOARD
from utils.auth import require_permission
from utils.dashboard_view import (
    EXPECTED_DASHBOARD_BUNDLE_SCHEMA_VERSION,
    DashboardViewContractError,
    build_attention_follow_up_rows,
    select_dashboard_mode_payload,
)
from utils.ui import (
    render_attention_required,
    render_dashboard_mode_status,
    render_dashboard_section_header,
    render_kpi_grid,
    render_operational_event_strip,
    render_operational_page_header,
)
from utils.formatting import (
    format_datetime, format_age, format_report_age, format_table_age,
    display_event_name, display_sitrep, counted_label
)

# --- SETUP & CONSTANTS ---

if not hasattr(dashboard_ui, "render_current_evacuation_picture"):
    dashboard_ui = importlib.reload(dashboard_ui)

render_current_evacuation_picture = dashboard_ui.render_current_evacuation_picture

if getattr(dashboard_service, "DASHBOARD_BUNDLE_SCHEMA_VERSION", 0) != EXPECTED_DASHBOARD_BUNDLE_SCHEMA_VERSION:
    dashboard_service = importlib.reload(dashboard_service)

current_user = require_permission(PERMISSION_VIEW_DASHBOARD)

MANILA_TIMEZONE = ZoneInfo("Asia/Manila")
PROVISIONAL_INCLUDED_STATUSES = {"Submitted", "For Validation", "Validated"}
EMPTY_RECONCILIATION_SUMMARY = {
    "match": 0, "mismatch": 0, "missing_source": 0, "allocation_conflict": 0, "no_current_data": 0,
}
PLOTLY_DASHBOARD_CONFIG = {"displayModeBar": False, "scrollZoom": False, "displaylogo": False}


# --- HELPER FUNCTIONS ---

def select_reconciliation_payload(
        dashboard: dict[str, Any], *, view_mode: str
) -> tuple[dict[str, Any], list[dict[str, Any]], bool, bool]:
    mode_specific_available = all(
        key in dashboard for key in (
            "provisional_reconciliation_summary", "provisional_reconciliation_rows",
            "provisional_reconciliation_available", "official_reconciliation_summary",
            "official_reconciliation_rows", "official_reconciliation_available"
        )
    )

    if view_mode == "Provisional Operational":
        summary_source = dashboard.get("provisional_reconciliation_summary",
                                       dashboard.get("reconciliation_summary", EMPTY_RECONCILIATION_SUMMARY))
        rows_source = dashboard.get("provisional_reconciliation_rows", dashboard.get("reconciliation_rows", []))
        available = bool(
            dashboard.get("provisional_reconciliation_available", dashboard.get("reconciliation_available", False)))
    elif mode_specific_available:
        summary_source = dashboard.get("official_reconciliation_summary", EMPTY_RECONCILIATION_SUMMARY)
        rows_source = dashboard.get("official_reconciliation_rows", [])
        available = bool(dashboard.get("official_reconciliation_available", False))
    else:
        summary_source = EMPTY_RECONCILIATION_SUMMARY
        rows_source = []
        available = False

    summary = dict(summary_source) if isinstance(summary_source, dict) else dict(EMPTY_RECONCILIATION_SUMMARY)
    rows = list(rows_source) if isinstance(rows_source, list) else []
    return summary, rows, available, mode_specific_available


def _counted_label(count: int, singular: str, plural: str | None = None) -> str:
    if count == 1: return singular
    return plural if plural is not None else f"{singular}s"





def record_is_included(record: dict[str, Any], *, view_mode: str) -> bool:
    validation_status = str(record["validation_status"])
    if view_mode == "Official Validated":
        return validation_status == "Validated"
    return validation_status in PROVISIONAL_INCLUDED_STATUSES


def event_display_name(active_event: dict[str, Any]) -> str:
    event_name = str(active_event["event_name"])
    classification = active_event.get("classification")
    if classification is not None and str(classification).strip():
        return f"{classification} {event_name}"
    return event_name


def format_road_status(value: Any) -> str:
    text = str(value)
    compact_labels = {
        "Passable to Large Vehicles Only": "Large vehicles only",
        "Passable to Small Vehicles Only": "Small vehicles only",
        "Passable to Light Vehicles Only": "Light vehicles only",
        "Passable with Difficulty": "Passable w/ difficulty",
        "Passable with Caution": "Passable w/ caution",
    }
    return compact_labels.get(text, text)


def format_table_age(value: datetime | None) -> str:
    if value is None: return "—"
    current = datetime.now(MANILA_TIMEZONE)
    localized = value.astimezone(MANILA_TIMEZONE)
    seconds = max(int((current - localized).total_seconds()), 0)
    if seconds < 60: return "<1m"
    minutes = seconds // 60
    if minutes < 60: return f"{minutes}m"
    hours = minutes // 60
    if hours < 24: return f"{hours}h"
    days = hours // 24
    return f"{days}d"


def format_optional_count(value: Any) -> str:
    if value is None: return "—"
    return f"{int(value):,}"


def build_barangay_table(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Barangay": row["barangay_name"], "Situation": row["situation_status"],
        "Affected Families": row["affected_families"], "Affected Individuals": row["affected_individuals"],
        "Inside EC": row["inside_ec_individuals"], "Outside EC": row["outside_ec_individuals"],
        "Road": row["road_status"], "Power": row["power_status"], "Water": row["water_status"],
        "Rescue": row["rescue_requests"], "Validation": row["validation_status"],
        "Report Age": format_age(row["recorded_at"]), "Recorded At": row["recorded_at"],
    } for row in rows])


def build_evacuation_table(rows: list[dict[str, Any]]) -> pd.DataFrame:
    table_rows = []
    for row in rows:
        individuals = int(row["individuals"])
        safe_capacity = int(row.get("safe_capacity") or 0)
        utilization = (individuals / safe_capacity) * 100 if safe_capacity > 0 else None
        table_rows.append({
            "Evacuation Center": row["center_name"], "Status": row["status"], "Families": row["families"],
            "Individuals": individuals, "Safe Capacity": safe_capacity,
            "Utilization %": round(utilization, 1) if utilization is not None else None,
            "Food": row["food_status"], "Water": row["water_status"], "Electricity": row["electricity_status"],
            "Medical Cases": row["medical_cases"], "Validation": row["validation_status"],
            "Report Age": format_age(row["recorded_at"]), "Recorded At": row["recorded_at"],
        })
    return pd.DataFrame(table_rows)


def build_barangay_operational_table(rows: list[dict[str, Any]]) -> pd.DataFrame:
    table_rows = []
    for row in rows:
        inside = int(row["inside_ec_individuals"])
        outside = int(row["outside_ec_individuals"])
        table_rows.append({
            "Barangay": row["barangay_name"], "Situation": row["situation_status"],
            "Affected (ind.)": int(row["affected_individuals"]), "Displaced (ind.)": inside + outside,
            "Road": format_road_status(row["road_status"]),
            "Power / Water": str(row["power_status"]) + " / " + str(row["water_status"]),
            "Rescue": int(row["rescue_requests"]), "Validation": row["validation_status"],
            "Report Age": format_table_age(row["recorded_at"]),
        })
    return pd.DataFrame(table_rows)


def build_evacuation_operational_table(rows: list[dict[str, Any]]) -> pd.DataFrame:
    table_rows = []
    for row in rows:
        individuals = int(row["individuals"])
        safe_capacity = int(row.get("safe_capacity") or 0)
        utilization = (individuals / safe_capacity) * 100 if safe_capacity > 0 else None
        occupancy = f"{individuals:,} / {safe_capacity:,} · {utilization:.1f}%" if utilization is not None else f"{individuals:,} / —"

        table_rows.append({
            "Evacuation Center": row["center_name"], "Status": row["status"], "Occupancy / Use": occupancy,
            "Food / Water": str(row["food_status"]) + " / " + str(row["water_status"]),
            "Power": row["electricity_status"], "Medical": int(row["medical_cases"]),
            "Validation": row["validation_status"], "Report Age": format_table_age(row["recorded_at"]),
        })
    return pd.DataFrame(table_rows)


def build_reconciliation_operational_table(rows: list[dict[str, Any]]) -> pd.DataFrame:
    table_rows = []
    status_labels = {
        "Match": "Matching Totals", "Mismatch": "Different Totals",
        "No Barangay Report": "Missing Barangay Report", "No EC Report": "Missing Center Report",
        "Allocation Conflict": "Assignment Conflict",
    }
    for row in rows:
        reconciliation_status = str(row["reconciliation_status"])
        table_rows.append({
            "Barangay": row["barangay_name"], "Status": status_labels.get(reconciliation_status, reconciliation_status),
            "Families — Barangay / EC": format_optional_count(
                row["barangay_inside_families"]) + " / " + format_optional_count(row["ec_inside_families"]),
            "Individuals — Barangay / EC": format_optional_count(
                row["barangay_inside_individuals"]) + " / " + format_optional_count(row["ec_inside_individuals"]),
            "Barangay Age": format_age(row["barangay_recorded_at"]),
            "EC Source Age": format_age(row["latest_ec_recorded_at"]),
        })
    return pd.DataFrame(table_rows)


def style_operational_chart(figure, *, height: int = 330) -> None:
    figure.update_layout(
        height=height, margin=dict(l=20, r=20, t=24, b=30),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#1A2540", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(namelength=-1),
    )
    figure.update_xaxes(gridcolor="#E5EAF2", zeroline=False, showline=False)
    figure.update_yaxes(gridcolor="#E5EAF2", zeroline=False, showline=False)


# --- RENDERER FUNCTIONS ---

def render_overview_section(
        summary: dict[str, Any],
        evacuation_summary: dict[str, Any],
        selected_rows: list[dict[str, Any]],
        evacuation_rows: list[dict[str, Any]],
        reconciliation_summary: dict[str, Any],
        reconciliation_rows: list[dict[str, Any]],
        reconciliation_available: bool,
        view_mode: str,
        render_current_evacuation_picture_func: Callable,
) -> None:
    """Renders the main overview KPIs, alerts, and evacuation summaries."""
    reconciliation_issue_count = (
            int(reconciliation_summary["mismatch"]) + int(reconciliation_summary["missing_source"]) + int(
        reconciliation_summary["allocation_conflict"])
    )

    pending_rescue_count = int(summary["pending_rescue_requests"])
    impassable_road_count = int(summary["impassable_roads"])
    power_interruption_count = int(summary["interrupted_power"])
    water_interruption_count = int(summary["interrupted_water"])
    over_capacity_center_count = int(evacuation_summary["over_capacity_centers"])
    medical_case_count = int(evacuation_summary["medical_cases"])
    population_consistency_count = int(summary["population_consistency_issues"])

    attention_specs = (
        (_counted_label(pending_rescue_count, "Pending Rescue Request"), pending_rescue_count, "danger"),
        (_counted_label(impassable_road_count, "Impassable Road"), impassable_road_count, "danger"),
        (_counted_label(power_interruption_count, "Power Interruption"), power_interruption_count, "warning"),
        (_counted_label(water_interruption_count, "Water Interruption"), water_interruption_count, "warning"),
        (_counted_label(over_capacity_center_count, "Over-Capacity Center"), over_capacity_center_count, "danger"),
        ("Critical Food", int(evacuation_summary["critical_food"]), "danger"),
        ("Critical Water", int(evacuation_summary["critical_water"]), "danger"),
        (_counted_label(medical_case_count, "Medical Case"), medical_case_count, "warning"),
        ("Pending Validation", int(summary["pending_validation"]), "warning"),
        ("Needs Correction", int(summary["needs_correction"]), "danger"),
        (_counted_label(population_consistency_count, "Population Consistency Issue"), population_consistency_count,
         "danger"),
        (_counted_label(reconciliation_issue_count, "Record Needs Data Checking", "Records Need Data Checking"),
         reconciliation_issue_count, "warning"),
    )

    attention_items = [{"label": label, "value": value, "tone": tone} for label, value, tone in attention_specs if
                       value > 0]
    if not reconciliation_available:
        attention_items.append({"label": "Population Reconciliation", "value": "Unavailable", "tone": "warning"})

    render_dashboard_section_header(title="Attention Required",
                                    subtitle="Current non-zero exceptions that may require operational review or follow-up.")
    render_attention_required(attention_items)

    attention_follow_up_rows = build_attention_follow_up_rows(
        barangay_rows=list(selected_rows), evacuation_rows=list(evacuation_rows),
        reconciliation_rows=reconciliation_rows,
    )

    if attention_follow_up_rows:
        with st.expander("Review the records behind these alerts", expanded=False):
            st.caption(
                "Use the Area and Location columns to find the matching record in the Barangays, Evacuation Centers, or Report Checks section below.")
            st.dataframe(
                attention_follow_up_rows, width="stretch", hide_index=True,
                column_order=("Area", "Location", "What needs review"),
                column_config={
                    "Area": st.column_config.TextColumn("Area", width=130),
                    "Location": st.column_config.TextColumn("Location", width=190),
                    "What needs review": st.column_config.TextColumn("What needs review", width="large"),
                },
            )
        # --- NON-DISPLACED POPULATION BLOCK ---
        render_dashboard_section_header(
            title="Non-Displaced Population",
            subtitle="Affected people who remain in their homes.",
        )

        render_kpi_grid(
            [
                {
                    "label": "Non-Displaced — Families",
                    "value": f"{int(summary['affected_not_displaced_families']):,}",
                },
                {
                    "label": "Non-Displaced — Individuals",
                    "value": f"{int(summary['affected_not_displaced_individuals']):,}",
                },
            ],
            compact=False,
        )
        # --------------------------------------
    render_dashboard_section_header(title="Current Evacuation Summary",
                                    subtitle="Affected population and current evacuation figures for the selected data mode.")
    render_current_evacuation_picture_func(
        affected_barangays=int(summary["affected_barangays"]), affected_families=int(summary["affected_families"]),
        affected_individuals=int(summary["affected_individuals"]),
        operational_centers=int(evacuation_summary["open_centers"]),
        inside_ec_families=int(summary["inside_ec_families"]),
        inside_ec_individuals=int(summary["inside_ec_individuals"]),
        outside_ec_families=int(summary["outside_ec_families"]),
        outside_ec_individuals=int(summary["outside_ec_individuals"]),
        mode_label=view_mode, barangay_as_of=format_datetime(summary["latest_update"]),
        center_as_of=format_datetime(evacuation_summary["latest_update"]),
    )

    render_dashboard_section_header(title="Reporting & Freshness",
                                    subtitle="Coverage, validation workload, and age of the current source reports.")
    render_kpi_grid([
        {"label": "Barangays Reporting",
         "value": f"{int(summary['reports_received'])} / {int(summary['total_barangays'])}",
         "meta": f"{float(summary['coverage_percent']):.1f}% coverage"},
        {"label": "Pending Validation", "value": f"{int(summary['pending_validation']):,}"},
        {"label": "Needs Correction", "value": f"{int(summary['needs_correction']):,}"},
        {"label": "Newest Barangay Report", "value": format_age(summary["latest_update"]),
         "meta": format_datetime(summary["latest_update"])},
        {"label": "Oldest Current Report", "value": format_age(summary["oldest_current_update"]),
         "meta": format_datetime(summary["oldest_current_update"])},
        {"label": "Newest EC Report", "value": format_age(evacuation_summary["latest_update"]),
         "meta": format_datetime(evacuation_summary["latest_update"])},
    ], compact=True)
    st.divider()


def render_barangay_section(selected_rows: list[dict[str, Any]], included_barangay_rows: list[dict[str, Any]]) -> None:
    """Renders the barangay operational table and analytical views."""
    render_dashboard_section_header(title="Barangay Operational Picture",
                                    subtitle="Routine view prioritizing current population impact, access, utilities, rescue demand, validation, and freshness.")

    if not selected_rows:
        st.info("No barangay reports are available in this dashboard mode.")
    else:
        st.dataframe(
            build_barangay_operational_table(selected_rows), width="stretch", hide_index=True,
            column_order=("Barangay", "Situation", "Affected (ind.)", "Displaced (ind.)", "Road", "Power / Water",
                          "Rescue", "Validation", "Report Age"),
            column_config={
                "Barangay": st.column_config.TextColumn("Barangay", width=150, pinned=True),
                "Situation": st.column_config.TextColumn("Situation", width=95),
                "Affected (ind.)": st.column_config.NumberColumn("Affected", help="Affected individuals", width=78,
                                                                 format="%d"),
                "Displaced (ind.)": st.column_config.NumberColumn("Displaced",
                                                                  help="Individuals recorded inside or outside evacuation centers",
                                                                  width=82, format="%d"),
                "Road": st.column_config.TextColumn("Road", width=175),
                "Power / Water": st.column_config.TextColumn("Power / Water", width=130),
                "Rescue": st.column_config.NumberColumn("Rescue", width=70, format="%d"),
                "Validation": st.column_config.TextColumn("Validation", width=100),
                "Report Age": st.column_config.TextColumn("Age", help="Age since the current report was recorded",
                                                          width=60),
            },
        )
        with st.expander("Full barangay source fields", expanded=False):
            st.caption(
                "Includes family counts, inside/outside EC split, individual utility fields, timestamps, and validation data.")
            st.dataframe(build_barangay_table(selected_rows), width="stretch", hide_index=True)

    affected_chart_rows = [{"Barangay": row["barangay_name"], "Affected Individuals": int(row["affected_individuals"])}
                           for row in included_barangay_rows if int(row["affected_individuals"]) > 0]
    displacement_rows = []
    for row in included_barangay_rows:
        inside, outside = int(row["inside_ec_individuals"]), int(row["outside_ec_individuals"])
        if inside > 0 or outside > 0:
            displacement_rows.extend((
                {"Barangay": row["barangay_name"], "Location": "Inside EC", "Individuals": inside},
                {"Barangay": row["barangay_name"], "Location": "Outside EC", "Individuals": outside},
            ))

    if affected_chart_rows or displacement_rows:
        with st.expander("Analytical views", expanded=False):
            if affected_chart_rows:
                st.markdown("**Most affected barangays**")
                affected_dataframe = pd.DataFrame(affected_chart_rows).sort_values("Affected Individuals",
                                                                                   ascending=False).head(
                    10).sort_values("Affected Individuals", ascending=True)
                affected_figure = px.bar(affected_dataframe, x="Affected Individuals", y="Barangay", orientation="h",
                                         text="Affected Individuals")
                affected_figure.update_traces(textposition="inside", cliponaxis=False)
                affected_figure.update_layout(showlegend=False)
                affected_figure.update_xaxes(title="Affected individuals")
                affected_figure.update_yaxes(title="")
                style_operational_chart(affected_figure)
                st.plotly_chart(affected_figure, width="stretch", config=PLOTLY_DASHBOARD_CONFIG)

            if displacement_rows:
                st.markdown("**Displacement location by barangay**")
                displacement_figure = px.bar(pd.DataFrame(displacement_rows), x="Barangay", y="Individuals",
                                             color="Location", barmode="stack")
                displacement_figure.update_xaxes(title="")
                displacement_figure.update_yaxes(title="Individuals")
                style_operational_chart(displacement_figure)
                st.plotly_chart(displacement_figure, width="stretch", config=PLOTLY_DASHBOARD_CONFIG)


def render_evacuation_section(evacuation_rows: list[dict[str, Any]], included_evacuation_rows: list[dict[str, Any]],
                              summary: dict[str, Any], evacuation_summary: dict[str, Any]) -> None:
    """Renders the evacuation center metrics, tables, and capacity charts."""
    render_dashboard_section_header(title="Evacuation Center Operations",
                                    subtitle="Current center status, occupancy, capacity, supplies, medical demand, validation, and report freshness.")
    render_kpi_grid([
        {"label": "Operational Centers", "value": f"{int(evacuation_summary['open_centers']):,}"},
        {"label": "Center-Reported Families", "value": f"{int(evacuation_summary['families']):,}"},
        {"label": "Center-Reported Individuals", "value": f"{int(evacuation_summary['individuals']):,}"},
        {"label": "Overall Capacity Use",
         "value": f"{float(evacuation_summary['capacity_utilization_percent']):.1f}%" if int(
             evacuation_summary["safe_capacity"]) > 0 else "No data"},
    ])

    barangay_inside_families, barangay_inside_individuals = int(summary["inside_ec_families"]), int(
        summary["inside_ec_individuals"])
    center_reported_families, center_reported_individuals = int(evacuation_summary["families"]), int(
        evacuation_summary["individuals"])

    if barangay_inside_families != center_reported_families or barangay_inside_individuals != center_reported_individuals:
        st.warning(
            f"Barangay and evacuation-center reports currently show different inside-center totals. Barangay reports: {barangay_inside_families:,} families / {barangay_inside_individuals:,} individuals. Center reports: {center_reported_families:,} families / {center_reported_individuals:,} individuals. Review Report Checks before publishing official figures.")

    if not evacuation_rows:
        st.info("No evacuation-center reports are available in this dashboard mode.")
    else:
        st.dataframe(
            build_evacuation_operational_table(evacuation_rows), width="stretch", hide_index=True,
            column_order=("Evacuation Center", "Status", "Occupancy / Use", "Food / Water", "Power", "Medical",
                          "Validation", "Report Age"),
            column_config={
                "Evacuation Center": st.column_config.TextColumn("Evacuation Center", width=240, pinned=True),
                "Status": st.column_config.TextColumn("Status", width=90),
                "Occupancy / Use": st.column_config.TextColumn("Occupancy / Use",
                                                               help="Individuals / safe capacity · utilization",
                                                               width=125),
                "Food / Water": st.column_config.TextColumn("Food / Water", width=130),
                "Power": st.column_config.TextColumn("Power", width=85),
                "Medical": st.column_config.NumberColumn("Medical", width=65, format="%d"),
                "Validation": st.column_config.TextColumn("Validation", width=95),
                "Report Age": st.column_config.TextColumn("Age", help="Age since the current report was recorded",
                                                          width=60),
            },
        )
        with st.expander("Full evacuation-center source fields", expanded=False):
            st.caption(
                "Includes families, exact safe capacity, individual supply fields, electricity, medical cases, timestamps, and validation data.")
            st.dataframe(build_evacuation_table(evacuation_rows), width="stretch", hide_index=True)

    capacity_chart_rows = []
    for row in included_evacuation_rows:
        individuals, safe_capacity = int(row["individuals"]), int(row.get("safe_capacity") or 0)
        if individuals > 0 or safe_capacity > 0:
            capacity_chart_rows.extend((
                {"Evacuation Center": row["center_name"], "Measure": "Occupants", "Individuals": individuals},
                {"Evacuation Center": row["center_name"], "Measure": "Safe Capacity", "Individuals": safe_capacity},
            ))

    if capacity_chart_rows:
        with st.expander("Capacity analytical view", expanded=False):
            capacity_figure = px.bar(pd.DataFrame(capacity_chart_rows), x="Evacuation Center", y="Individuals",
                                     color="Measure", barmode="group")
            capacity_figure.update_xaxes(title="")
            capacity_figure.update_yaxes(title="Individuals")
            style_operational_chart(capacity_figure)
            st.plotly_chart(capacity_figure, width="stretch", config=PLOTLY_DASHBOARD_CONFIG)


def render_reconciliation_section(reconciliation_summary: dict[str, Any], reconciliation_rows: list[dict[str, Any]],
                                  reconciliation_available: bool) -> None:
    """Renders the report consistency checks and data verification tables."""
    render_dashboard_section_header(title="Report Consistency Checks",
                                    subtitle="Compare inside-evacuation-center totals reported by barangays with totals assigned by evacuation centers. Differences show what needs verification; they do not automatically mean a record is wrong.")
    render_kpi_grid([
        {"label": "Matching Barangays", "value": f"{int(reconciliation_summary['match']):,}"},
        {"label": "Different Totals", "value": f"{int(reconciliation_summary['mismatch']):,}"},
        {"label": "Missing Report", "value": f"{int(reconciliation_summary['missing_source']):,}"},
        {"label": "Assignment Conflicts", "value": f"{int(reconciliation_summary['allocation_conflict']):,}"},
    ])

    if not reconciliation_available:
        st.warning("Report consistency checks could not be loaded. The main dashboard figures remain available.")
        return

    problem_rows = [row for row in reconciliation_rows if
                    row["reconciliation_status"] in {"Mismatch", "No Barangay Report", "No EC Report",
                                                     "Allocation Conflict"}]

    if not problem_rows:
        st.success("Barangay and evacuation-center totals currently agree, and no source report is missing.")
    else:
        issue_label = _counted_label(len(problem_rows), "barangay currently requires", "barangays currently require")
        st.warning(f"{len(problem_rows)} {issue_label} a report comparison or a missing source report.")
        st.dataframe(
            build_reconciliation_operational_table(problem_rows), width="stretch", hide_index=True,
            column_order=("Barangay", "Status", "Families — Barangay / EC", "Individuals — Barangay / EC",
                          "Barangay Age", "EC Source Age"),
            column_config={
                "Barangay": st.column_config.TextColumn("Barangay", width=150, pinned=True),
                "Status": st.column_config.TextColumn("Status", width=145),
                "Families — Barangay / EC": st.column_config.TextColumn("Families: Barangay / Center",
                                                                        help="First number: barangay reported. Second: EC assigned.",
                                                                        width=180),
                "Individuals — Barangay / EC": st.column_config.TextColumn("Individuals: Barangay / Center",
                                                                           help="First number: barangay reported. Second: EC assigned.",
                                                                           width=190),
                "Barangay Age": st.column_config.TextColumn("Barangay Age", width=110),
                "EC Source Age": st.column_config.TextColumn("Center Report Age", width=110),
            },
        )
        with st.expander("View separate totals and source timestamps", expanded=False):
            st.dataframe(pd.DataFrame([{
                "Barangay": row["barangay_name"], "Status": row["reconciliation_status"],
                "Barangay-Reported Inside-Center Families": row["barangay_inside_families"],
                "Center-Reported Families for Barangay": row["ec_inside_families"],
                "Barangay-Reported Inside-Center Individuals": row["barangay_inside_individuals"],
                "Center-Reported Individuals for Barangay": row["ec_inside_individuals"],
                "Barangay Report": row["barangay_recorded_at"], "Latest Center Report": row["latest_ec_recorded_at"],
            } for row in problem_rows]), width="stretch", hide_index=True)

    st.caption(
        "Before correcting or publishing official figures, compare timestamps and source documents. This checking view remains a warning workflow and does not rewrite operational reports.")


# --- MAIN EXECUTION BLOCK ---

render_operational_page_header(title="Situation Dashboard",
                               subtitle="Current operational picture for the active disaster event.")

refresh_column, mode_column = st.columns([1, 4], vertical_alignment="bottom")

with refresh_column:
    if st.button("Refresh data", icon=":material/refresh:", width="stretch"):
        st.rerun()

with mode_column:
    if "dashboard_view_mode" not in st.session_state:
        st.session_state.dashboard_view_mode = "Provisional Operational"

    view_mode = st.radio(
        "Data mode",
        options=("Provisional Operational", "Official Validated"),
        horizontal=True,
        help="Provisional uses the latest submitted operational reports. Official uses the latest report that has completed validation.",
        key="dashboard_view_mode"
    )

try:
    dashboard = dashboard_service.get_dashboard_bundle()
except dashboard_service.DashboardDataIntegrityError as error:
    st.error(str(error))
    st.stop()
except dashboard_service.DashboardServiceError as error:
    st.error(str(error))
    st.stop()
except Exception:
    st.error("The dashboard could not be loaded. Contact the system administrator if the problem continues.")
    st.stop()

active_event = dashboard.get("active_event")
if active_event is None:
    st.warning("No active disaster event exists. Create an event through Event Control first.")
    st.stop()

sitrep_value = active_event.get("current_sitrep_number")
sitrep_text = str(sitrep_value) if sitrep_value not in {None, ""} else "Not set"
reference = active_event.get("official_reference")
overview = active_event.get("situation_overview")

render_operational_event_strip(
    event_name=event_display_name(active_event), hazard_type=str(active_event["hazard_type"]),
    alert_code=str(active_event["alert_code"]), eoc_status=str(active_event["eoc_status"]),
    sitrep=sitrep_text, official_reference=str(reference) if reference else None,
)

if overview:
    with st.expander("Current situation overview", expanded=False):
        st.write(overview)

try:
    mode_payload = select_dashboard_mode_payload(dashboard, view_mode=view_mode)
except DashboardViewContractError:
    st.error(
        "The dashboard data service did not return one complete and consistent view. Refresh the page. If the problem continues, contact the system administrator.")
    st.stop()

summary = mode_payload["summary"]
selected_rows = mode_payload["rows"]
evacuation_summary = mode_payload["evacuation_summary"]
evacuation_rows = mode_payload["evacuation_rows"]

reconciliation_summary, reconciliation_rows, reconciliation_available, _ = select_reconciliation_payload(dashboard,
                                                                                                         view_mode=view_mode)
render_dashboard_mode_status(mode=view_mode)

if summary is None or evacuation_summary is None:
    st.info("No dashboard summary is available for this event.")
    st.stop()

included_barangay_rows = [row for row in selected_rows if record_is_included(row, view_mode=view_mode)]
included_evacuation_rows = [row for row in evacuation_rows if record_is_included(row, view_mode=view_mode)]

# 1. Render Overview
render_overview_section(
    summary=summary, evacuation_summary=evacuation_summary,
    selected_rows=selected_rows, evacuation_rows=evacuation_rows,
    reconciliation_summary=reconciliation_summary, reconciliation_rows=reconciliation_rows,
    reconciliation_available=reconciliation_available, view_mode=view_mode,
    render_current_evacuation_picture_func=render_current_evacuation_picture
)

# 2. Render Tabs
global_reconciliation_issue_count = int(reconciliation_summary["mismatch"]) + int(
    reconciliation_summary["missing_source"]) + int(reconciliation_summary["allocation_conflict"])

barangay_tab, evacuation_tab, quality_tab = st.tabs((
    f"Barangays ({len(selected_rows)})",
    f"Evacuation Centers ({len(evacuation_rows)})",
    f"Report Checks ({global_reconciliation_issue_count})",
))

with barangay_tab:
    render_barangay_section(selected_rows, included_barangay_rows)

with evacuation_tab:
    render_evacuation_section(evacuation_rows, included_evacuation_rows, summary, evacuation_summary)

with quality_tab:
    render_reconciliation_section(reconciliation_summary, reconciliation_rows, reconciliation_available)