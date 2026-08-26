from datetime import datetime
from decimal import Decimal
from typing import Any

from database.connection import SessionLocal
from database.repositories import (
    fetch_active_barangays,
    fetch_active_event_rows,
    fetch_latest_barangay_updates_for_event,
    fetch_latest_evacuation_updates_for_event,
)
from services.validation_service import (
    ValidationServiceError,
    get_population_reconciliation_queue,
)
from utils.dashboard_view import (
    ActiveEvent, DashboardSummary, EvacuationSummary,
    BarangayRow, EvacuationRow, ReconciliationRow
)


class DashboardServiceError(Exception):
    """Base exception for dashboard operations."""


class DashboardDataIntegrityError(DashboardServiceError):
    """Raised when inconsistent operational data is found."""


PROVISIONAL_USABLE_STATUSES = {"Submitted", "For Validation", "Validated"}
DASHBOARD_BUNDLE_SCHEMA_VERSION = 2


def _safe_int(value: Any) -> int:
    if value is None: return 0
    if isinstance(value, Decimal): return int(value)
    return int(value)


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"Submitted": 0, "For Validation": 0, "Validated": 0, "Needs Correction": 0, "Superseded": 0, "Other": 0}
    for row in rows:
        status = str(row["validation_status"])
        if status in counts:
            counts[status] += 1
        else:
            counts["Other"] += 1
    return counts


def _timestamps(rows: list[dict[str, Any]]) -> tuple[datetime | None, datetime | None]:
    values = [row["recorded_at"] for row in rows if row.get("recorded_at") is not None]
    if not values: return None, None
    return max(values), min(values)


def _build_summary(*, rows: list[dict[str, Any]], total_barangays: int, usable_statuses: set[str]) -> DashboardSummary:
    usable_rows = [row for row in rows if str(row["validation_status"]) in usable_statuses]

    affected_barangays = sum(1 for row in usable_rows if
                             (_safe_int(row["affected_families"]) > 0 or _safe_int(row["affected_individuals"]) > 0))
    affected_families = sum(_safe_int(row["affected_families"]) for row in usable_rows)
    affected_individuals = sum(_safe_int(row["affected_individuals"]) for row in usable_rows)

    inside_ec_families = sum(_safe_int(row["inside_ec_families"]) for row in usable_rows)
    inside_ec_individuals = sum(_safe_int(row["inside_ec_individuals"]) for row in usable_rows)
    outside_ec_families = sum(_safe_int(row["outside_ec_families"]) for row in usable_rows)
    outside_ec_individuals = sum(_safe_int(row["outside_ec_individuals"]) for row in usable_rows)

    displaced_families = inside_ec_families + outside_ec_families
    displaced_individuals = inside_ec_individuals + outside_ec_individuals
    affected_not_displaced_families = affected_families - displaced_families
    affected_not_displaced_individuals = affected_individuals - displaced_individuals

    population_consistency_issues = sum(
        1 for row in usable_rows
        if (_safe_int(row["inside_ec_families"]) + _safe_int(row["outside_ec_families"]) > _safe_int(
            row["affected_families"]) or
            (_safe_int(row["inside_ec_individuals"]) + _safe_int(row["outside_ec_individuals"]) > _safe_int(
                row["affected_individuals"])))
    )

    pending_rescue_requests = sum(_safe_int(row["rescue_requests"]) for row in usable_rows)
    impassable_roads = sum(1 for row in usable_rows if row["road_status"] == "Impassable")
    interrupted_power = sum(1 for row in usable_rows if row["power_status"] == "Interrupted")
    interrupted_water = sum(1 for row in usable_rows if row["water_status"] == "Interrupted")

    status_counts = _status_counts(rows)
    latest_update, oldest_current_update = _timestamps(usable_rows)
    reports_received = len(rows)
    coverage_percent = ((reports_received / total_barangays) * 100 if total_barangays > 0 else 0.0)

    return {
        "affected_barangays": affected_barangays,
        "affected_families": affected_families,
        "affected_individuals": affected_individuals,
        "inside_ec_families": inside_ec_families,
        "inside_ec_individuals": inside_ec_individuals,
        "outside_ec_families": outside_ec_families,
        "outside_ec_individuals": outside_ec_individuals,
        "affected_not_displaced_families": affected_not_displaced_families,
        "affected_not_displaced_individuals": affected_not_displaced_individuals,
        "population_consistency_issues": population_consistency_issues,
        "pending_rescue_requests": pending_rescue_requests,
        "impassable_roads": impassable_roads,
        "interrupted_power": interrupted_power,
        "interrupted_water": interrupted_water,
        "pending_validation": status_counts["Submitted"] + status_counts["For Validation"],
        "needs_correction": status_counts["Needs Correction"],
        "reports_received": reports_received,
        "total_barangays": total_barangays,
        "coverage_percent": coverage_percent,
        "latest_update": latest_update,
        "oldest_current_update": oldest_current_update,
    }


def _build_evacuation_summary(*, rows: list[dict[str, Any]], usable_statuses: set[str]) -> EvacuationSummary:
    usable_rows = [row for row in rows if str(row["validation_status"]) in usable_statuses]
    operational_statuses = {"Open", "Full", "Over Capacity"}
    operational_rows = [row for row in usable_rows if row["status"] in operational_statuses]

    open_centers = len(operational_rows)
    over_capacity_centers = sum(1 for row in operational_rows if row["status"] == "Over Capacity")
    families = sum(_safe_int(row["families"]) for row in operational_rows)
    individuals = sum(_safe_int(row["individuals"]) for row in operational_rows)
    safe_capacity = sum(max(_safe_int(row.get("safe_capacity")), 0) for row in operational_rows)

    capacity_utilization_percent = ((individuals / safe_capacity) * 100 if safe_capacity > 0 else 0.0)
    medical_cases = sum(_safe_int(row["medical_cases"]) for row in operational_rows)
    critical_food = sum(1 for row in operational_rows if row["food_status"] in {"Critical", "Unavailable"})
    critical_water = sum(1 for row in operational_rows if row["water_status"] in {"Critical", "Unavailable"})
    latest_update, _ = _timestamps(usable_rows)

    return {
        "open_centers": open_centers,
        "families": families,
        "individuals": individuals,
        "safe_capacity": safe_capacity,
        "capacity_utilization_percent": capacity_utilization_percent,
        "over_capacity_centers": over_capacity_centers,
        "critical_food": critical_food,
        "critical_water": critical_water,
        "medical_cases": medical_cases,
        "latest_update": latest_update,
    }


def _build_reconciliation_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"match": 0, "mismatch": 0, "missing_source": 0, "allocation_conflict": 0, "no_current_data": 0}
    for row in rows:
        status = str(row.get("reconciliation_status", "No Current Data"))
        if status == "Match":
            counts["match"] += 1
        elif status == "Mismatch":
            counts["mismatch"] += 1
        elif status == "Allocation Conflict":
            counts["allocation_conflict"] += 1
        elif status in {"No Barangay Report", "No EC Report"}:
            counts["missing_source"] += 1
        else:
            counts["no_current_data"] += 1
    return counts


def get_active_event_helper(session: Any) -> ActiveEvent | None:
    """Helper to safely fetch the singular active event."""
    active_events = fetch_active_event_rows(session)
    if len(active_events) > 1:
        raise DashboardDataIntegrityError("More than one active disaster event exists.")
    if not active_events:
        return None
    return dict(active_events[0])  # type: ignore


def get_dashboard_bundle() -> dict[str, Any]:
    """Build one read-only operational dashboard payload efficiently."""
    try:
        with SessionLocal() as session:
            active_event = get_active_event_helper(session)

            if not active_event:
                empty_recon = _build_reconciliation_summary([])
                return {
                    "schema_version": DASHBOARD_BUNDLE_SCHEMA_VERSION,
                    "active_event": None, "provisional_summary": None, "official_summary": None,
                    "provisional_rows": [], "official_rows": [],
                    "provisional_evacuation_summary": None, "official_evacuation_summary": None,
                    "provisional_evacuation_rows": [], "official_evacuation_rows": [],
                    "provisional_reconciliation_rows": [], "official_reconciliation_rows": [],
                    "provisional_reconciliation_summary": empty_recon, "official_reconciliation_summary": empty_recon,
                    "provisional_reconciliation_available": True, "official_reconciliation_available": True,
                    "reconciliation_rows": [], "reconciliation_summary": empty_recon, "reconciliation_available": True,
                }

            event_id = active_event["id"]
            total_barangays = len(fetch_active_barangays(session))

            latest_all_rows = [dict(row) for row in fetch_latest_barangay_updates_for_event(session, event_id=event_id)]
            latest_validated_rows = [row for row in latest_all_rows if row["validation_status"] == "Validated"]

            provisional_summary = _build_summary(rows=latest_all_rows, total_barangays=total_barangays,
                                                 usable_statuses=PROVISIONAL_USABLE_STATUSES)
            official_summary = _build_summary(rows=latest_validated_rows, total_barangays=total_barangays,
                                              usable_statuses={"Validated"})

            latest_evacuation_rows = [dict(row) for row in
                                      fetch_latest_evacuation_updates_for_event(session, event_id=event_id)]
            latest_validated_evacuation_rows = [row for row in latest_evacuation_rows if
                                                row["validation_status"] == "Validated"]

            provisional_evacuation_summary = _build_evacuation_summary(rows=latest_evacuation_rows,
                                                                       usable_statuses=PROVISIONAL_USABLE_STATUSES)
            official_evacuation_summary = _build_evacuation_summary(rows=latest_validated_evacuation_rows,
                                                                    usable_statuses={"Validated"})

            bundle = {
                "schema_version": DASHBOARD_BUNDLE_SCHEMA_VERSION,
                "active_event": active_event,
                "provisional_summary": provisional_summary, "official_summary": official_summary,
                "provisional_rows": latest_all_rows, "official_rows": latest_validated_rows,
                "provisional_evacuation_summary": provisional_evacuation_summary,
                "official_evacuation_summary": official_evacuation_summary,
                "provisional_evacuation_rows": latest_evacuation_rows,
                "official_evacuation_rows": latest_validated_evacuation_rows,
            }

            try:
                # We still need to call the validation service, but we reuse the existing active event context
                provisional_reconciliation_rows = get_population_reconciliation_queue(
                    included_statuses=("Submitted", "For Validation", "Validated"))
            except ValidationServiceError:
                provisional_reconciliation_rows, provisional_reconciliation_available = [], False
            else:
                provisional_reconciliation_available = True

            try:
                official_reconciliation_rows = get_population_reconciliation_queue(included_statuses=("Validated",))
            except ValidationServiceError:
                official_reconciliation_rows, official_reconciliation_available = [], False
            else:
                official_reconciliation_available = True

            bundle.update({
                "provisional_reconciliation_rows": provisional_reconciliation_rows,
                "official_reconciliation_rows": official_reconciliation_rows,
                "provisional_reconciliation_summary": _build_reconciliation_summary(provisional_reconciliation_rows),
                "official_reconciliation_summary": _build_reconciliation_summary(official_reconciliation_rows),
                "provisional_reconciliation_available": provisional_reconciliation_available,
                "official_reconciliation_available": official_reconciliation_available,
                "reconciliation_rows": provisional_reconciliation_rows,
                "reconciliation_summary": _build_reconciliation_summary(provisional_reconciliation_rows),
                "reconciliation_available": provisional_reconciliation_available,
            })

            return bundle

    except DashboardServiceError:
        raise
    except Exception as error:
        raise DashboardServiceError("The dashboard data could not be retrieved from PostgreSQL.") from error