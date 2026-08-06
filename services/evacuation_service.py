from database.connection import SessionLocal, session_scope
from database.models import (
    EvacuationCenter,
    EvacuationCenterUpdate,
)
from database.repositories import (
    fetch_active_barangays,
    fetch_active_event_rows,
    fetch_active_evacuation_centers,
    fetch_barangay_by_id,
    fetch_evacuation_center_by_id,
    fetch_evacuation_center_by_name_barangay,
    fetch_recent_evacuation_center_updates,
)


class EvacuationServiceError(Exception):
    """Base evacuation-center service exception."""


class EvacuationValidationError(EvacuationServiceError):
    """Raised when submitted values are invalid."""


class EvacuationDataIntegrityError(EvacuationServiceError):
    """Raised when inconsistent records are detected."""


class NoActiveEventError(EvacuationServiceError):
    """Raised when no active disaster event exists."""


def list_active_evacuation_centers() -> list[dict[str, object]]:
    """
    Retrieve all active evacuation centers.
    """
    try:
        with SessionLocal() as session:
            rows = fetch_active_evacuation_centers(session)

            return [
                dict(row)
                for row in rows
            ]

    except Exception as error:
        raise EvacuationServiceError(
            "Unable to retrieve evacuation centers."
        ) from error


def create_evacuation_center(
    *,
    name: str,
    barangay_id: int,
    address: str | None,
    safe_capacity: int,
) -> int:
    """
    Create a permanent evacuation-center master record.
    """
    cleaned_name = name.strip()

    if not cleaned_name:
        raise EvacuationValidationError(
            "Evacuation-center name is required."
        )

    if barangay_id <= 0:
        raise EvacuationValidationError(
            "A valid barangay is required."
        )

    if safe_capacity < 0:
        raise EvacuationValidationError(
            "Safe capacity cannot be negative."
        )

    with session_scope() as session:
        barangay = fetch_barangay_by_id(
            session,
            barangay_id,
        )

        if barangay is None:
            raise EvacuationValidationError(
                "The selected barangay does not exist "
                "or is inactive."
            )

        duplicate = (
            fetch_evacuation_center_by_name_barangay(
                session,
                name=cleaned_name,
                barangay_id=barangay_id,
            )
        )

        if duplicate is not None:
            raise EvacuationValidationError(
                "An evacuation center with this name "
                "already exists in the selected barangay."
            )

        center = EvacuationCenter(
            name=cleaned_name,
            barangay_id=barangay_id,
            address=(
                address.strip()
                if address and address.strip()
                else None
            ),
            safe_capacity=safe_capacity,
            is_active=True,
        )

        session.add(center)
        session.flush()

        return center.id


def create_evacuation_center_update(
    *,
    center_id: int,
    status: str,
    families: int,
    individuals: int,
    children: int,
    senior_citizens: int,
    pwd: int,
    pregnant_women: int,
    medical_cases: int,
    food_status: str,
    water_status: str,
    electricity_status: str,
    sanitation_status: str,
    source: str,
    remarks: str | None,
) -> int:
    """
    Save a new historical evacuation-center update.
    """
    cleaned_source = source.strip()
    cleaned_sanitation = sanitation_status.strip()

    if center_id <= 0:
        raise EvacuationValidationError(
            "A valid evacuation center is required."
        )

    if not cleaned_source:
        raise EvacuationValidationError(
            "Information source is required."
        )

    if not cleaned_sanitation:
        raise EvacuationValidationError(
            "Sanitation status is required."
        )

    counts = {
        "Families": families,
        "Individuals": individuals,
        "Children": children,
        "Senior citizens": senior_citizens,
        "PWD": pwd,
        "Pregnant women": pregnant_women,
        "Medical cases": medical_cases,
    }

    for label, value in counts.items():
        if value < 0:
            raise EvacuationValidationError(
                f"{label} cannot be negative."
            )

    if individuals < families:
        raise EvacuationValidationError(
            "Individuals cannot be lower than families."
        )

    vulnerable_counts = {
        "Children": children,
        "Senior citizens": senior_citizens,
        "PWD": pwd,
        "Pregnant women": pregnant_women,
        "Medical cases": medical_cases,
    }

    for label, value in vulnerable_counts.items():
        if value > individuals:
            raise EvacuationValidationError(
                f"{label} cannot exceed the total "
                "number of individuals."
            )

    with session_scope() as session:
        active_events = fetch_active_event_rows(session)

        if len(active_events) > 1:
            raise EvacuationDataIntegrityError(
                "More than one active disaster event exists."
            )

        if not active_events:
            raise NoActiveEventError(
                "Create an active disaster event first."
            )

        center = fetch_evacuation_center_by_id(
            session,
            center_id=center_id,
        )

        if center is None:
            raise EvacuationValidationError(
                "The selected evacuation center does not "
                "exist or is inactive."
            )

        event_id = int(active_events[0]["id"])

        update = EvacuationCenterUpdate(
            event_id=event_id,
            evacuation_center_id=center.id,
            status=status,
            families=families,
            individuals=individuals,
            children=children,
            senior_citizens=senior_citizens,
            pwd=pwd,
            pregnant_women=pregnant_women,
            medical_cases=medical_cases,
            food_status=food_status,
            water_status=water_status,
            electricity_status=electricity_status,
            sanitation_status=cleaned_sanitation,
            source=cleaned_source,
            validation_status="Submitted",
            remarks=(
                remarks.strip()
                if remarks and remarks.strip()
                else None
            ),
        )

        session.add(update)
        session.flush()

        return update.id


def get_recent_evacuation_updates(
    *,
    limit: int = 20,
) -> list[dict[str, object]]:
    """
    Retrieve recent center updates for the active event.
    """
    with SessionLocal() as session:
        active_events = fetch_active_event_rows(session)

        if len(active_events) > 1:
            raise EvacuationDataIntegrityError(
                "More than one active disaster event exists."
            )

        if not active_events:
            return []

        event_id = int(active_events[0]["id"])

        rows = fetch_recent_evacuation_center_updates(
            session,
            event_id=event_id,
            limit=limit,
        )

        return [
            dict(row)
            for row in rows
        ]