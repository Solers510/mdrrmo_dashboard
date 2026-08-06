from decimal import Decimal

from database.connection import SessionLocal, session_scope
from database.models import BarangayUpdate
from database.repositories import (
    fetch_active_barangays,
    fetch_active_event_rows,
    fetch_barangay_by_id,
    fetch_recent_barangay_updates,
)


class BarangayServiceError(Exception):
    """Base exception for barangay-service operations."""


class BarangayValidationError(BarangayServiceError):
    """Raised when submitted barangay data is invalid."""


class BarangayDataIntegrityError(BarangayServiceError):
    """Raised when inconsistent database data is detected."""


class NoActiveEventError(BarangayServiceError):
    """Raised when no active disaster event exists."""


def list_active_barangays() -> list[dict[str, object]]:
    """
    Retrieve all active Naic barangays from PostgreSQL.
    """
    try:
        with SessionLocal() as session:
            rows = fetch_active_barangays(session)

            return [
                dict(row)
                for row in rows
            ]

    except Exception as error:
        raise BarangayServiceError(
            "Unable to retrieve barangays from PostgreSQL."
        ) from error


def get_recent_barangay_updates(
    *,
    limit: int = 20,
) -> list[dict[str, object]]:
    """
    Retrieve recent updates belonging to the active event.
    """
    with SessionLocal() as session:
        active_events = fetch_active_event_rows(session)

        if len(active_events) > 1:
            raise BarangayDataIntegrityError(
                "More than one active disaster event exists."
            )

        if not active_events:
            return []

        event_id = int(active_events[0]["id"])

        rows = fetch_recent_barangay_updates(
            session,
            event_id=event_id,
            limit=limit,
        )

        return [
            dict(row)
            for row in rows
        ]


def create_barangay_update(
    *,
    barangay_id: int,
    situation_status: str,
    affected_families: int,
    affected_individuals: int,
    inside_ec_families: int,
    inside_ec_individuals: int,
    outside_ec_families: int,
    outside_ec_individuals: int,
    flood_status: str,
    flood_depth_cm: float,
    road_status: str,
    power_status: str,
    water_status: str,
    rescue_requests: int,
    source: str,
    remarks: str | None,
) -> int:
    """
    Save a new historical barangay update.

    The function returns the new database record ID.
    """
    cleaned_source = source.strip()

    if barangay_id <= 0:
        raise BarangayValidationError(
            "A valid barangay is required."
        )

    if not cleaned_source:
        raise BarangayValidationError(
            "Information source is required."
        )

    numeric_values = {
        "Affected families": affected_families,
        "Affected individuals": affected_individuals,
        "Inside-EC families": inside_ec_families,
        "Inside-EC individuals": inside_ec_individuals,
        "Outside-EC families": outside_ec_families,
        "Outside-EC individuals": outside_ec_individuals,
        "Rescue requests": rescue_requests,
    }

    for label, value in numeric_values.items():
        if value < 0:
            raise BarangayValidationError(
                f"{label} cannot be negative."
            )

    if flood_depth_cm < 0:
        raise BarangayValidationError(
            "Flood depth cannot be negative."
        )

    if affected_individuals < affected_families:
        raise BarangayValidationError(
            "Affected individuals cannot be lower than "
            "affected families."
        )

    if inside_ec_individuals < inside_ec_families:
        raise BarangayValidationError(
            "Individuals inside evacuation centers cannot "
            "be lower than families inside evacuation centers."
        )

    if outside_ec_individuals < outside_ec_families:
        raise BarangayValidationError(
            "Individuals outside evacuation centers cannot "
            "be lower than families outside evacuation centers."
        )

    displaced_families = (
        inside_ec_families
        + outside_ec_families
    )

    displaced_individuals = (
        inside_ec_individuals
        + outside_ec_individuals
    )

    if displaced_families > affected_families:
        raise BarangayValidationError(
            "Inside-EC and outside-EC families combined "
            "cannot exceed total affected families."
        )

    if displaced_individuals > affected_individuals:
        raise BarangayValidationError(
            "Inside-EC and outside-EC individuals combined "
            "cannot exceed total affected individuals."
        )

    with session_scope() as session:
        active_events = fetch_active_event_rows(session)

        if len(active_events) > 1:
            raise BarangayDataIntegrityError(
                "More than one active disaster event exists. "
                "Correct the event records before saving."
            )

        if not active_events:
            raise NoActiveEventError(
                "No active disaster event exists. "
                "Create an event in Event Control first."
            )

        barangay = fetch_barangay_by_id(
            session,
            barangay_id,
        )

        if barangay is None:
            raise BarangayValidationError(
                "The selected barangay does not exist "
                "or is inactive."
            )

        event_id = int(active_events[0]["id"])

        update = BarangayUpdate(
            event_id=event_id,
            barangay_id=barangay.id,
            situation_status=situation_status,
            affected_families=affected_families,
            affected_individuals=affected_individuals,
            inside_ec_families=inside_ec_families,
            inside_ec_individuals=inside_ec_individuals,
            outside_ec_families=outside_ec_families,
            outside_ec_individuals=outside_ec_individuals,
            flood_status=flood_status,
            flood_depth_cm=Decimal(
                str(flood_depth_cm)
            ),
            road_status=road_status,
            power_status=power_status,
            water_status=water_status,
            rescue_requests=rescue_requests,
            source=cleaned_source,
            validation_status="Submitted",
            remarks=(
                remarks.strip()
                if remarks and remarks.strip()
                else None
            ),
        )

        session.add(update)

        # Execute the INSERT so PostgreSQL assigns the ID.
        session.flush()

        return update.id