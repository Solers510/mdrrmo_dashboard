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


class DashboardServiceError(Exception):
    """Base exception for dashboard operations."""


class DashboardDataIntegrityError(DashboardServiceError):
    """Raised when inconsistent operational data is found."""


PROVISIONAL_USABLE_STATUSES = {
    "Submitted",
    "For Validation",
    "Validated",
}

DASHBOARD_BUNDLE_SCHEMA_VERSION = 2


def _safe_int(value: Any) -> int:
    if value is None:
        return 0

    if isinstance(value, Decimal):
        return int(value)

    return int(value)


def _status_counts(
    rows: list[dict[str, object]],
) -> dict[str, int]:
    counts = {
        "Submitted": 0,
        "For Validation": 0,
        "Validated": 0,
        "Needs Correction": 0,
        "Superseded": 0,
        "Other": 0,
    }

    for row in rows:
        status = str(row["validation_status"])
        if status in counts:
            counts[status] += 1
        else:
            counts["Other"] += 1

    return counts


def _timestamps(
    rows: list[dict[str, object]],
) -> tuple[datetime | None, datetime | None]:
    values = [
        row["recorded_at"]
        for row in rows
        if row.get("recorded_at") is not None
    ]

    if not values:
        return None, None

    return max(values), min(values)


def _build_summary(
    *,
    rows: list[dict[str, object]],
    total_barangays: int,
    usable_statuses: set[str],
) -> dict[str, object]:
    usable_rows = [
        row
        for row in rows
        if str(row["validation_status"]) in usable_statuses
    ]

    affected_barangays = sum(
        1
        for row in usable_rows
        if (
            _safe_int(row["affected_families"]) > 0
            or _safe_int(row["affected_individuals"]) > 0
        )
    )

    affected_families = sum(
        _safe_int(row["affected_families"])
        for row in usable_rows
    )
    affected_individuals = sum(
        _safe_int(row["affected_individuals"])
        for row in usable_rows
    )

    inside_ec_families = sum(
        _safe_int(row["inside_ec_families"])
        for row in usable_rows
    )
    inside_ec_individuals = sum(
        _safe_int(row["inside_ec_individuals"])
        for row in usable_rows
    )
    inside_ec_barangays = sum(
        1
        for row in usable_rows
        if (
            _safe_int(row["inside_ec_families"]) > 0
            or _safe_int(row["inside_ec_individuals"]) > 0
        )
    )

    outside_ec_families = sum(
        _safe_int(row["outside_ec_families"])
        for row in usable_rows
    )
    outside_ec_individuals = sum(
        _safe_int(row["outside_ec_individuals"])
        for row in usable_rows
    )
    outside_ec_barangays = sum(
        1
        for row in usable_rows
        if (
            _safe_int(row["outside_ec_families"]) > 0
            or _safe_int(row["outside_ec_individuals"]) > 0
        )
    )

    displaced_families = (
        inside_ec_families
        + outside_ec_families
    )
    displaced_individuals = (
        inside_ec_individuals
        + outside_ec_individuals
    )

    affected_not_displaced_families = (
        affected_families
        - displaced_families
    )
    affected_not_displaced_individuals = (
        affected_individuals
        - displaced_individuals
    )

    population_consistency_issues = sum(
        1
        for row in usable_rows
        if (
            _safe_int(row["inside_ec_families"])
            + _safe_int(row["outside_ec_families"])
            > _safe_int(row["affected_families"])
            or (
                _safe_int(row["inside_ec_individuals"])
                + _safe_int(row["outside_ec_individuals"])
                > _safe_int(row["affected_individuals"])
            )
        )
    )

    pending_rescue_requests = sum(
        _safe_int(row["rescue_requests"])
        for row in usable_rows
    )

    impassable_roads = sum(
        1
        for row in usable_rows
        if row["road_status"] == "Impassable"
    )

    interrupted_power = sum(
        1
        for row in usable_rows
        if row["power_status"] == "Interrupted"
    )

    interrupted_water = sum(
        1
        for row in usable_rows
        if row["water_status"] == "Interrupted"
    )

    status_counts = _status_counts(rows)
    latest_update, oldest_current_update = _timestamps(
        usable_rows
    )

    reports_received = len(rows)
    usable_reports = len(usable_rows)
    missing_reports = max(
        total_barangays - reports_received,
        0,
    )

    coverage_percent = (
        (reports_received / total_barangays) * 100
        if total_barangays > 0
        else 0.0
    )

    return {
        "affected_barangays": affected_barangays,
        "affected_families": affected_families,
        "affected_individuals": affected_individuals,
        "inside_ec_families": inside_ec_families,
        "inside_ec_individuals": inside_ec_individuals,
        "inside_ec_barangays": inside_ec_barangays,
        "outside_ec_families": outside_ec_families,
        "outside_ec_individuals": outside_ec_individuals,
        "outside_ec_barangays": outside_ec_barangays,
        "displaced_families": displaced_families,
        "displaced_individuals": displaced_individuals,
        "affected_not_displaced_families": (
            affected_not_displaced_families
        ),
        "affected_not_displaced_individuals": (
            affected_not_displaced_individuals
        ),
        "population_consistency_issues": (
            population_consistency_issues
        ),
        "pending_rescue_requests": pending_rescue_requests,
        "impassable_roads": impassable_roads,
        "interrupted_power": interrupted_power,
        "interrupted_water": interrupted_water,
        "reports_received": reports_received,
        "usable_reports": usable_reports,
        "missing_reports": missing_reports,
        "coverage_percent": coverage_percent,
        "needs_correction": status_counts["Needs Correction"],
        "pending_validation": (
            status_counts["Submitted"]
            + status_counts["For Validation"]
        ),
        "validated_reports": status_counts["Validated"],
        "status_counts": status_counts,
        "total_barangays": total_barangays,
        "latest_update": latest_update,
        "oldest_current_update": oldest_current_update,
    }


def _build_evacuation_summary(
    *,
    rows: list[dict[str, object]],
    usable_statuses: set[str],
) -> dict[str, object]:
    usable_rows = [
        row
        for row in rows
        if str(row["validation_status"]) in usable_statuses
    ]

    operational_statuses = {
        "Open",
        "Full",
        "Over Capacity",
    }

    operational_rows = [
        row
        for row in usable_rows
        if row["status"] in operational_statuses
    ]

    open_centers = len(operational_rows)
    full_centers = sum(
        1
        for row in operational_rows
        if row["status"] == "Full"
    )
    over_capacity_centers = sum(
        1
        for row in operational_rows
        if row["status"] == "Over Capacity"
    )

    families = sum(
        _safe_int(row["families"])
        for row in operational_rows
    )
    individuals = sum(
        _safe_int(row["individuals"])
        for row in operational_rows
    )

    safe_capacity = sum(
        max(_safe_int(row.get("safe_capacity")), 0)
        for row in operational_rows
    )

    capacity_utilization_percent = (
        (individuals / safe_capacity) * 100
        if safe_capacity > 0
        else 0.0
    )

    children = sum(
        _safe_int(row["children"])
        for row in operational_rows
    )
    senior_citizens = sum(
        _safe_int(row["senior_citizens"])
        for row in operational_rows
    )
    pwd = sum(
        _safe_int(row["pwd"])
        for row in operational_rows
    )
    pregnant_women = sum(
        _safe_int(row["pregnant_women"])
        for row in operational_rows
    )
    medical_cases = sum(
        _safe_int(row["medical_cases"])
        for row in operational_rows
    )

    critical_food = sum(
        1
        for row in operational_rows
        if row["food_status"] in {
            "Critical",
            "Unavailable",
        }
    )
    critical_water = sum(
        1
        for row in operational_rows
        if row["water_status"] in {
            "Critical",
            "Unavailable",
        }
    )
    unavailable_electricity = sum(
        1
        for row in operational_rows
        if row["electricity_status"] == "Unavailable"
    )

    latest_update, oldest_current_update = _timestamps(
        usable_rows
    )
    status_counts = _status_counts(rows)

    return {
        "open_centers": open_centers,
        "full_centers": full_centers,
        "over_capacity_centers": over_capacity_centers,
        "families": families,
        "individuals": individuals,
        "safe_capacity": safe_capacity,
        "capacity_utilization_percent": (
            capacity_utilization_percent
        ),
        "children": children,
        "senior_citizens": senior_citizens,
        "pwd": pwd,
        "pregnant_women": pregnant_women,
        "medical_cases": medical_cases,
        "critical_food": critical_food,
        "critical_water": critical_water,
        "unavailable_electricity": unavailable_electricity,
        "reports_received": len(rows),
        "reports_included": len(usable_rows),
        "needs_correction": status_counts["Needs Correction"],
        "pending_validation": (
            status_counts["Submitted"]
            + status_counts["For Validation"]
        ),
        "validated_reports": status_counts["Validated"],
        "status_counts": status_counts,
        "latest_update": latest_update,
        "oldest_current_update": oldest_current_update,
    }


def _build_reconciliation_summary(
    rows: list[dict[str, object]],
) -> dict[str, int]:
    counts = {
        "match": 0,
        "mismatch": 0,
        "missing_source": 0,
        "allocation_conflict": 0,
        "no_current_data": 0,
    }

    for row in rows:
        status = str(
            row.get(
                "reconciliation_status",
                "No Current Data",
            )
        )

        if status == "Match":
            counts["match"] += 1
        elif status == "Mismatch":
            counts["mismatch"] += 1
        elif status == "Allocation Conflict":
            counts["allocation_conflict"] += 1
        elif status in {
            "No Barangay Report",
            "No EC Report",
        }:
            counts["missing_source"] += 1
        else:
            counts["no_current_data"] += 1

    return counts


def get_dashboard_bundle() -> dict[str, object]:
    """
    Build one read-only operational dashboard payload.

    The dashboard uses the latest report per source and preserves a
    separate provisional-versus-validated view. Population reconciliation
    remains an operational quality check and is not used to rewrite data.
    """
    try:
        with SessionLocal() as session:
            active_events = fetch_active_event_rows(
                session
            )

            if len(active_events) > 1:
                raise DashboardDataIntegrityError(
                    "More than one active disaster event exists."
                )

            if not active_events:
                return {
                    "schema_version": DASHBOARD_BUNDLE_SCHEMA_VERSION,
                    "active_event": None,
                    "provisional_summary": None,
                    "official_summary": None,
                    "provisional_rows": [],
                    "official_rows": [],
                    "provisional_evacuation_summary": None,
                    "official_evacuation_summary": None,
                    "provisional_evacuation_rows": [],
                    "official_evacuation_rows": [],
                    "provisional_reconciliation_rows": [],
                    "official_reconciliation_rows": [],
                    "provisional_reconciliation_summary": (
                        _build_reconciliation_summary([])
                    ),
                    "official_reconciliation_summary": (
                        _build_reconciliation_summary([])
                    ),
                    "provisional_reconciliation_available": True,
                    "official_reconciliation_available": True,
                    "reconciliation_rows": [],
                    "reconciliation_summary": (
                        _build_reconciliation_summary([])
                    ),
                    "reconciliation_available": True,
                }

            active_event = dict(
                active_events[0]
            )
            event_id = int(
                active_event["id"]
            )

            barangays = fetch_active_barangays(
                session
            )
            total_barangays = len(
                barangays
            )

            latest_all_rows = [
                dict(row)
                for row in fetch_latest_barangay_updates_for_event(
                    session,
                    event_id=event_id,
                )
            ]

            latest_validated_rows = [
                dict(row)
                for row in fetch_latest_barangay_updates_for_event(
                    session,
                    event_id=event_id,
                    included_statuses=(
                        "Validated",
                    ),
                )
            ]

            provisional_summary = _build_summary(
                rows=latest_all_rows,
                total_barangays=total_barangays,
                usable_statuses=(
                    PROVISIONAL_USABLE_STATUSES
                ),
            )

            official_summary = _build_summary(
                rows=latest_validated_rows,
                total_barangays=total_barangays,
                usable_statuses={
                    "Validated",
                },
            )

            latest_evacuation_rows = [
                dict(row)
                for row in fetch_latest_evacuation_updates_for_event(
                    session,
                    event_id=event_id,
                )
            ]

            latest_validated_evacuation_rows = [
                dict(row)
                for row in fetch_latest_evacuation_updates_for_event(
                    session,
                    event_id=event_id,
                    included_statuses=(
                        "Validated",
                    ),
                )
            ]

            provisional_evacuation_summary = (
                _build_evacuation_summary(
                    rows=latest_evacuation_rows,
                    usable_statuses=(
                        PROVISIONAL_USABLE_STATUSES
                    ),
                )
            )

            official_evacuation_summary = (
                _build_evacuation_summary(
                    rows=(
                        latest_validated_evacuation_rows
                    ),
                    usable_statuses={
                        "Validated",
                    },
                )
            )

            bundle = {
                "schema_version": DASHBOARD_BUNDLE_SCHEMA_VERSION,
                "active_event": active_event,
                "provisional_summary": (
                    provisional_summary
                ),
                "official_summary": (
                    official_summary
                ),
                "provisional_rows": (
                    latest_all_rows
                ),
                "official_rows": (
                    latest_validated_rows
                ),
                "provisional_evacuation_summary": (
                    provisional_evacuation_summary
                ),
                "official_evacuation_summary": (
                    official_evacuation_summary
                ),
                "provisional_evacuation_rows": (
                    latest_evacuation_rows
                ),
                "official_evacuation_rows": (
                    latest_validated_evacuation_rows
                ),
            }

        try:
            provisional_reconciliation_rows = (
                get_population_reconciliation_queue(
                    included_statuses=(
                        "Submitted",
                        "For Validation",
                        "Validated",
                    ),
                )
            )
        except ValidationServiceError:
            provisional_reconciliation_rows = []
            provisional_reconciliation_available = False
        else:
            provisional_reconciliation_available = True

        try:
            official_reconciliation_rows = (
                get_population_reconciliation_queue(
                    included_statuses=("Validated",),
                )
            )
        except ValidationServiceError:
            official_reconciliation_rows = []
            official_reconciliation_available = False
        else:
            official_reconciliation_available = True

        bundle["provisional_reconciliation_rows"] = (
            provisional_reconciliation_rows
        )
        bundle["official_reconciliation_rows"] = (
            official_reconciliation_rows
        )
        bundle["provisional_reconciliation_summary"] = (
            _build_reconciliation_summary(
                provisional_reconciliation_rows
            )
        )
        bundle["official_reconciliation_summary"] = (
            _build_reconciliation_summary(
                official_reconciliation_rows
            )
        )
        bundle["provisional_reconciliation_available"] = (
            provisional_reconciliation_available
        )
        bundle["official_reconciliation_available"] = (
            official_reconciliation_available
        )

        # Backward-compatible aliases retain the provisional operational
        # meaning used before mode-specific reconciliation was introduced.
        bundle["reconciliation_rows"] = (
            provisional_reconciliation_rows
        )
        bundle["reconciliation_summary"] = (
            bundle["provisional_reconciliation_summary"]
        )
        bundle["reconciliation_available"] = (
            provisional_reconciliation_available
        )

        return bundle

    except DashboardServiceError:
        raise

    except Exception as error:
        raise DashboardServiceError(
            "The dashboard data could not be retrieved "
            "from PostgreSQL."
        ) from error
