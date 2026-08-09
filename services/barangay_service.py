from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from config.access_control import (
    PERMISSION_SUBMIT_BARANGAY_UPDATES,
    permissions_for_role,
)
from database.connection import SessionLocal, session_scope
from database.models import BarangayUpdate
from database.repositories import (
    fetch_active_barangays,
    fetch_active_event_rows,
    fetch_app_user_by_id,
    fetch_barangay_by_id,
    fetch_barangay_update_by_submission_key,
    fetch_latest_evacuation_updates_for_barangay,
    fetch_recent_barangay_updates,
)
from services.data_integrity import (
    DataIntegrityValidationError,
    reconcile_population,
    validate_flood_consistency,
    validate_submission_key,
)


USABLE_OPERATIONAL_STATUSES = (
    "Submitted",
    "For Validation",
    "Validated",
)

ACTIVE_CENTER_STATUSES = {
    "Open",
    "Full",
    "Over Capacity",
}


class BarangayServiceError(Exception):
    """Base exception for barangay-service operations."""


class BarangayValidationError(BarangayServiceError):
    """Raised when submitted barangay data is invalid."""


class BarangayAuthorizationError(BarangayServiceError):
    """Raised when the authenticated user cannot submit reports."""


class BarangayDataIntegrityError(BarangayServiceError):
    """Raised when inconsistent database data is detected."""


class DuplicateBarangaySubmissionError(BarangayServiceError):
    """Raised when the same form submission is received twice."""


class NoActiveEventError(BarangayServiceError):
    """Raised when no active disaster event exists."""


def _require_submitter(session, *, user_id: int):
    user = fetch_app_user_by_id(
        session,
        user_id=user_id,
    )

    if user is None or not user.is_active:
        raise BarangayAuthorizationError(
            "Your application account is not active."
        )

    if (
        PERMISSION_SUBMIT_BARANGAY_UPDATES
        not in permissions_for_role(user.role)
    ):
        raise BarangayAuthorizationError(
            "Your account is not authorized to submit barangay reports."
        )

    return user


def _inside_totals(rows) -> tuple[int, int, int, object | None]:
    active_rows = [
        row
        for row in rows
        if row["status"] in ACTIVE_CENTER_STATUSES
    ]

    families = sum(
        int(row["families"])
        for row in active_rows
    )
    individuals = sum(
        int(row["individuals"])
        for row in active_rows
    )

    timestamps = [
        row["recorded_at"]
        for row in rows
        if row["recorded_at"] is not None
    ]

    return (
        families,
        individuals,
        len(active_rows),
        max(timestamps) if timestamps else None,
    )


def list_active_barangays() -> list[dict[str, object]]:
    try:
        with SessionLocal() as session:
            return [
                dict(row)
                for row in fetch_active_barangays(session)
            ]
    except Exception as error:
        raise BarangayServiceError(
            "Unable to retrieve barangays from PostgreSQL."
        ) from error


def get_barangay_entry_context(
    *,
    barangay_id: int,
) -> dict[str, object]:
    """Return automatic inside-EC totals for the selected barangay."""
    with SessionLocal() as session:
        active_events = fetch_active_event_rows(session)

        if len(active_events) > 1:
            raise BarangayDataIntegrityError(
                "More than one active disaster event exists."
            )

        if not active_events:
            raise NoActiveEventError(
                "No active disaster event exists."
            )

        barangay = fetch_barangay_by_id(
            session,
            barangay_id,
        )
        if barangay is None:
            raise BarangayValidationError(
                "The selected barangay does not exist or is inactive."
            )

        event_id = int(active_events[0]["id"])
        rows = fetch_latest_evacuation_updates_for_barangay(
            session,
            event_id=event_id,
            barangay_id=barangay_id,
            included_statuses=USABLE_OPERATIONAL_STATUSES,
        )

        families, individuals, open_centers, latest_at = (
            _inside_totals(rows)
        )

        return {
            "event_id": event_id,
            "inside_ec_families": families,
            "inside_ec_individuals": individuals,
            "operational_centers": open_centers,
            "latest_ec_update": latest_at,
        }


def get_recent_barangay_updates(
    *,
    limit: int = 20,
) -> list[dict[str, object]]:
    with SessionLocal() as session:
        active_events = fetch_active_event_rows(session)

        if len(active_events) > 1:
            raise BarangayDataIntegrityError(
                "More than one active disaster event exists."
            )

        if not active_events:
            return []

        rows = fetch_recent_barangay_updates(
            session,
            event_id=int(active_events[0]["id"]),
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
    submission_key: str,
    submitter_user_id: int,
) -> int:
    cleaned_source = source.strip()

    if barangay_id <= 0:
        raise BarangayValidationError(
            "A valid barangay is required."
        )

    if not cleaned_source:
        raise BarangayValidationError(
            "Information source is required."
        )

    if rescue_requests < 0:
        raise BarangayValidationError(
            "Rescue requests cannot be negative."
        )

    try:
        canonical_key = validate_submission_key(
            submission_key
        )
        validate_flood_consistency(
            flood_status=flood_status,
            flood_depth_cm=flood_depth_cm,
        )
    except DataIntegrityValidationError as error:
        raise BarangayValidationError(
            str(error)
        ) from error

    try:
        with session_scope() as session:
            submitter = _require_submitter(
                session,
                user_id=submitter_user_id,
            )

            duplicate = (
                fetch_barangay_update_by_submission_key(
                    session,
                    submission_key=canonical_key,
                )
            )
            if duplicate is not None:
                raise DuplicateBarangaySubmissionError(
                    "This report was already saved. "
                    "The duplicate submission was ignored."
                )

            active_events = fetch_active_event_rows(
                session
            )

            if len(active_events) > 1:
                raise BarangayDataIntegrityError(
                    "More than one active disaster event exists."
                )

            if not active_events:
                raise NoActiveEventError(
                    "No active disaster event exists. "
                    "Create an event first."
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

            event_id = int(
                active_events[0]["id"]
            )

            try:
                reconcile_population(
                    affected_families=affected_families,
                    affected_individuals=affected_individuals,
                    inside_ec_families=inside_ec_families,
                    inside_ec_individuals=inside_ec_individuals,
                    outside_ec_families=outside_ec_families,
                    outside_ec_individuals=outside_ec_individuals,
                )
            except DataIntegrityValidationError as error:
                raise BarangayValidationError(
                    str(error)
                ) from error

            update = BarangayUpdate(
                event_id=event_id,
                barangay_id=barangay.id,
                submission_key=canonical_key,
                submitted_by_user_id=submitter.id,
                submitted_by=(
                    f"{submitter.display_name} — "
                    f"{submitter.role}"
                ),
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
            session.flush()

            return int(update.id)

    except IntegrityError as error:
        if (
            "uq_barangay_updates_submission_key"
            in str(error.orig)
        ):
            raise DuplicateBarangaySubmissionError(
                "This report was already saved. "
                "The duplicate submission was ignored."
            ) from error
        raise
