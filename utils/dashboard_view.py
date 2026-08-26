from typing import Any, TypedDict
from datetime import datetime

EXPECTED_DASHBOARD_BUNDLE_SCHEMA_VERSION = 2

SUPPORTED_DASHBOARD_MODES = {
    "Provisional Operational": "provisional",
    "Official Validated": "official",
}


class DashboardViewContractError(Exception):
    """Raised when the dashboard service and page disagree on payload shape."""


# --- STRICT DATA CONTRACTS (TYPED DICTS) ---

class ActiveEvent(TypedDict):
    id: int
    event_name: str
    hazard_type: str
    classification: str | None
    alert_code: str
    eoc_status: str
    current_sitrep_number: str | None
    official_reference: str | None
    situation_overview: str | None
    started_at: datetime


class DashboardSummary(TypedDict):
    affected_barangays: int
    affected_families: int
    affected_individuals: int
    inside_ec_families: int
    inside_ec_individuals: int
    outside_ec_families: int
    outside_ec_individuals: int
    affected_not_displaced_families: int
    affected_not_displaced_individuals: int
    pending_rescue_requests: int
    impassable_roads: int
    interrupted_power: int
    interrupted_water: int
    population_consistency_issues: int
    pending_validation: int
    needs_correction: int
    reports_received: int
    total_barangays: int
    coverage_percent: float
    latest_update: datetime | None
    oldest_current_update: datetime | None


class EvacuationSummary(TypedDict):
    open_centers: int
    families: int
    individuals: int
    safe_capacity: int
    capacity_utilization_percent: float
    over_capacity_centers: int
    critical_food: int
    critical_water: int
    medical_cases: int
    latest_update: datetime | None


class BarangayRow(TypedDict):
    barangay_name: str
    situation_status: str
    affected_families: int
    affected_individuals: int
    inside_ec_families: int
    inside_ec_individuals: int
    outside_ec_families: int
    outside_ec_individuals: int
    road_status: str
    power_status: str
    water_status: str
    rescue_requests: int
    validation_status: str
    recorded_at: datetime | None


class EvacuationRow(TypedDict):
    center_name: str
    barangay_name: str
    status: str
    families: int
    individuals: int
    safe_capacity: int | None
    food_status: str
    water_status: str
    electricity_status: str
    medical_cases: int
    validation_status: str
    recorded_at: datetime | None


class ReconciliationRow(TypedDict):
    barangay_name: str
    reconciliation_status: str
    barangay_inside_families: int | None
    barangay_inside_individuals: int | None
    ec_inside_families: int | None
    ec_inside_individuals: int | None
    barangay_recorded_at: datetime | None
    latest_ec_recorded_at: datetime | None


class DashboardPayload(TypedDict):
    mode: str
    summary: DashboardSummary
    rows: list[BarangayRow]
    evacuation_summary: EvacuationSummary
    evacuation_rows: list[EvacuationRow]


# --- VIEW LOGIC ---

def select_dashboard_mode_payload(
        dashboard: dict[str, Any], *, view_mode: str
) -> DashboardPayload:
    """Return one complete mode-specific payload or fail before rendering."""
    schema_version = int(dashboard.get("schema_version", 0) or 0)
    if schema_version != EXPECTED_DASHBOARD_BUNDLE_SCHEMA_VERSION:
        raise DashboardViewContractError("The dashboard data contract is out of date.")

    prefix = SUPPORTED_DASHBOARD_MODES.get(view_mode)
    if prefix is None:
        raise DashboardViewContractError("The selected dashboard data mode is not supported.")

    required_keys = {
        "summary": f"{prefix}_summary",
        "rows": f"{prefix}_rows",
        "evacuation_summary": f"{prefix}_evacuation_summary",
        "evacuation_rows": f"{prefix}_evacuation_rows",
    }
    missing_keys = [source_key for source_key in required_keys.values() if source_key not in dashboard]
    if missing_keys:
        raise DashboardViewContractError("The selected dashboard view is incomplete.")

    payload = {target_key: dashboard[source_key] for target_key, source_key in required_keys.items()}

    if not isinstance(payload["summary"], dict) or not isinstance(payload["evacuation_summary"], dict):
        raise DashboardViewContractError("The selected dashboard summaries are invalid.")
    if not isinstance(payload["rows"], list) or not isinstance(payload["evacuation_rows"], list):
        raise DashboardViewContractError("The selected dashboard record lists are invalid.")

    payload["mode"] = view_mode
    return payload  # type: ignore


def _safe_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(value)


def build_attention_follow_up_rows(
        *,
        barangay_rows: list[BarangayRow],
        evacuation_rows: list[EvacuationRow],
        reconciliation_rows: list[ReconciliationRow],
) -> list[dict[str, str]]:
    """Identify the source records behind the dashboard attention cards."""
    details: list[dict[str, str]] = []

    def add(*, area: str, location: str, issue: str) -> None:
        details.append({"Area": area, "Location": location, "What needs review": issue})

    for row in barangay_rows:
        location = str(row.get("barangay_name") or "Barangay not identified")
        rescue_requests = _safe_int(row.get("rescue_requests"))

        if rescue_requests > 0:
            add(area="Barangay", location=location,
                issue=f"{rescue_requests} pending rescue request{'s' if rescue_requests != 1 else ''}")

        if row.get("road_status") == "Impassable":
            add(area="Barangay", location=location, issue="Road reported as impassable")
        if row.get("power_status") == "Interrupted":
            add(area="Barangay", location=location, issue="Power service reported as interrupted")
        if row.get("water_status") == "Interrupted":
            add(area="Barangay", location=location, issue="Water service reported as interrupted")

        status = str(row.get("validation_status") or "")
        if status in {"Submitted", "For Validation"}:
            add(area="Barangay", location=location, issue="Current report is awaiting validation")
        elif status == "Needs Correction":
            add(area="Barangay", location=location, issue="Current report was returned for correction")

        affected_families = _safe_int(row.get("affected_families"))
        affected_individuals = _safe_int(row.get("affected_individuals"))
        evacuated_families = _safe_int(row.get("inside_ec_families")) + _safe_int(row.get("outside_ec_families"))
        evacuated_individuals = _safe_int(row.get("inside_ec_individuals")) + _safe_int(
            row.get("outside_ec_individuals"))

        if evacuated_families > affected_families or evacuated_individuals > affected_individuals:
            add(area="Barangay", location=location, issue="Evacuation totals exceed the reported affected population")

    active_center_statuses = {"Open", "Full", "Over Capacity"}
    for ec_row in evacuation_rows:
        if ec_row.get("status") not in active_center_statuses:
            continue

        location = str(ec_row.get("center_name") or "Evacuation center not identified")
        if ec_row.get("status") == "Over Capacity":
            add(area="Evacuation Center", location=location, issue="Center is reported over safe capacity")
        if ec_row.get("food_status") in {"Critical", "Unavailable"}:
            add(area="Evacuation Center", location=location, issue="Food supply needs urgent review")
        if ec_row.get("water_status") in {"Critical", "Unavailable"}:
            add(area="Evacuation Center", location=location, issue="Water supply needs urgent review")

        medical_cases = _safe_int(ec_row.get("medical_cases"))
        if medical_cases > 0:
            add(area="Evacuation Center", location=location,
                issue=f"{medical_cases} medical case{'s' if medical_cases != 1 else ''} recorded")

    reconciliation_messages = {
        "Mismatch": "Barangay and evacuation-center inside-EC totals differ",
        "No Barangay Report": "Evacuation-center occupants have no current barangay report",
        "No EC Report": "Barangay inside-EC figures have no current center report",
        "Allocation Conflict": "Cross-barangay allocation exceeds a center total",
    }

    for rec_row in reconciliation_rows:
        status = str(rec_row.get("reconciliation_status") or "")
        message = reconciliation_messages.get(status)
        if message is None:
            continue
        add(area="Report Check", location=str(rec_row.get("barangay_name") or "Barangay not identified"), issue=message)

    return details