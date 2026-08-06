from datetime import datetime
from decimal import Decimal
from typing import Any

from database.connection import SessionLocal
from database.repositories import (
    fetch_active_barangays,
    fetch_active_event_rows,
    fetch_latest_barangay_updates_for_event,
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


def _safe_int(value: Any) -> int:
    """
    Convert database numeric values to integers safely.
    """
    if value is None:
        return 0

    if isinstance(value, Decimal):
        return int(value)

    return int(value)


def _build_summary(
    *,
    rows: list[dict[str, object]],
    total_barangays: int,
    usable_statuses: set[str],
) -> dict[str, object]:
    """
    Calculate dashboard totals using only usable rows.
    """

    usable_rows = [
        row
        for row in rows
        if str(row["validation_status"])
        in usable_statuses
    ]

    affected_statuses = {
        "Affected",
        "Critical",
    }

    affected_barangays = sum(
        1
        for row in usable_rows
        if row["situation_status"]
        in affected_statuses
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

    outside_ec_families = sum(
        _safe_int(row["outside_ec_families"])
        for row in usable_rows
    )

    outside_ec_individuals = sum(
        _safe_int(row["outside_ec_individuals"])
        for row in usable_rows
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

    needs_correction = sum(
        1
        for row in rows
        if row["validation_status"]
        == "Needs Correction"
    )

    latest_update: datetime | None = None

    timestamps = [
        row["recorded_at"]
        for row in rows
        if row["recorded_at"] is not None
    ]

    if timestamps:
        latest_update = max(timestamps)

    reports_received = len(rows)

    missing_reports = max(
        total_barangays - reports_received,
        0,
    )

    return {
        "affected_barangays": affected_barangays,
        "affected_families": affected_families,
        "affected_individuals": affected_individuals,
        "inside_ec_families": inside_ec_families,
        "inside_ec_individuals": inside_ec_individuals,
        "outside_ec_families": outside_ec_families,
        "outside_ec_individuals": outside_ec_individuals,
        "pending_rescue_requests": (
            pending_rescue_requests
        ),
        "impassable_roads": impassable_roads,
        "interrupted_power": interrupted_power,
        "interrupted_water": interrupted_water,
        "reports_received": reports_received,
        "usable_reports": len(usable_rows),
        "missing_reports": missing_reports,
        "needs_correction": needs_correction,
        "total_barangays": total_barangays,
        "latest_update": latest_update,
    }


def get_dashboard_bundle() -> dict[str, object]:
    """
    Retrieve the active event and calculate both provisional
    and validated dashboard summaries.
    """

    try:
        with SessionLocal() as session:
            active_events = fetch_active_event_rows(
                session
            )

            if len(active_events) > 1:
                raise DashboardDataIntegrityError(
                    "More than one active disaster event "
                    "exists."
                )

            if not active_events:
                return {
                    "active_event": None,
                    "provisional_summary": None,
                    "official_summary": None,
                    "provisional_rows": [],
                    "official_rows": [],
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

            # Latest record regardless of validation status.
            latest_all_rows = [
                dict(row)
                for row in (
                    fetch_latest_barangay_updates_for_event(
                        session,
                        event_id=event_id,
                    )
                )
            ]

            # Latest validated record for each barangay.
            latest_validated_rows = [
                dict(row)
                for row in (
                    fetch_latest_barangay_updates_for_event(
                        session,
                        event_id=event_id,
                        included_statuses=(
                            "Validated",
                        ),
                    )
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

            return {
                "active_event": active_event,
                "provisional_summary": (
                    provisional_summary
                ),
                "official_summary": official_summary,
                "provisional_rows": latest_all_rows,
                "official_rows": (
                    latest_validated_rows
                ),
            }

    except DashboardServiceError:
        raise

    except Exception as error:
        raise DashboardServiceError(
            "The dashboard data could not be retrieved "
            "from PostgreSQL."
        ) from error