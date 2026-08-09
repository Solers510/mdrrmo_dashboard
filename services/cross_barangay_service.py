from uuid import UUID

from config.access_control import (
    PERMISSION_MANAGE_EVACUATION_CENTERS,
    permissions_for_role,
)
from database.connection import SessionLocal, session_scope
from database.models import CrossBarangayEvacuationAllocation
from database.repositories import (
    fetch_active_event_rows,
    fetch_active_barangays,
    fetch_app_user_by_id,
    fetch_barangay_by_id,
    fetch_cross_allocation_by_submission_key,
    fetch_evacuation_center_by_id,
    fetch_latest_cross_allocations_for_center,
    fetch_latest_cross_allocations_for_event,
    fetch_latest_evacuation_update_for_center,
)


USABLE_EC_STATUSES = (
    "Submitted",
    "For Validation",
    "Validated",
    "Needs Correction",
)


class CrossBarangayServiceError(Exception):
    """Base exception for cross-barangay evacuation allocation."""


class CrossBarangayValidationError(CrossBarangayServiceError):
    """Raised when allocation figures are invalid."""


class CrossBarangayAuthorizationError(CrossBarangayServiceError):
    """Raised when the account cannot record the exception."""


class CrossBarangayDataIntegrityError(CrossBarangayServiceError):
    """Raised when operational data is inconsistent."""


class DuplicateCrossBarangaySubmissionError(
    CrossBarangayServiceError
):
    """Raised when the same allocation form is submitted twice."""


def validate_cross_allocation(
    *,
    families: int,
    individuals: int,
    other_families: int,
    other_individuals: int,
    center_families: int,
    center_individuals: int,
) -> None:
    values = (
        families,
        individuals,
        other_families,
        other_individuals,
        center_families,
        center_individuals,
    )

    if any(value < 0 for value in values):
        raise CrossBarangayValidationError(
            "Allocation and occupancy figures cannot be negative."
        )

    if families > individuals:
        raise CrossBarangayValidationError(
            "Allocated families cannot exceed allocated individuals."
        )

    if (
        other_families + families
        > center_families
    ):
        raise CrossBarangayValidationError(
            "Total foreign-origin family allocations would exceed "
            "the latest evacuation-center family occupancy."
        )

    if (
        other_individuals + individuals
        > center_individuals
    ):
        raise CrossBarangayValidationError(
            "Total foreign-origin individual allocations would exceed "
            "the latest evacuation-center individual occupancy."
        )


def _canonical_submission_key(value: str) -> str:
    try:
        return str(UUID(value.strip()))
    except (AttributeError, TypeError, ValueError) as error:
        raise CrossBarangayValidationError(
            "The submission token is invalid. Refresh and try again."
        ) from error


def _active_event_id(session) -> int:
    rows = fetch_active_event_rows(session)

    if len(rows) > 1:
        raise CrossBarangayDataIntegrityError(
            "More than one active disaster event exists."
        )

    if not rows:
        raise CrossBarangayValidationError(
            "No active disaster event exists."
        )

    return int(rows[0]["id"])


def _require_manager(
    session,
    *,
    user_id: int,
):
    user = fetch_app_user_by_id(
        session,
        user_id=user_id,
    )

    if user is None or not user.is_active:
        raise CrossBarangayAuthorizationError(
            "Your application account is not active."
        )

    if (
        PERMISSION_MANAGE_EVACUATION_CENTERS
        not in permissions_for_role(user.role)
    ):
        raise CrossBarangayAuthorizationError(
            "Only authorized operations staff may record "
            "cross-barangay evacuation allocations."
        )

    return user


def get_cross_barangay_context(
    *,
    center_id: int,
) -> dict[str, object]:
    with SessionLocal() as session:
        event_id = _active_event_id(session)

        center = fetch_evacuation_center_by_id(
            session,
            center_id=center_id,
        )

        if center is None:
            raise CrossBarangayValidationError(
                "The selected evacuation center does not exist or is inactive."
            )

        latest_update = fetch_latest_evacuation_update_for_center(
            session,
            event_id=event_id,
            center_id=center_id,
            included_statuses=USABLE_EC_STATUSES,
        )

        allocations = fetch_latest_cross_allocations_for_center(
            session,
            event_id=event_id,
            center_id=center_id,
        )

        positive_allocations = [
            dict(row)
            for row in allocations
            if (
                int(row["families"]) > 0
                or int(row["individuals"]) > 0
            )
        ]

        return {
            "event_id": event_id,
            "center_id": int(center.id),
            "host_barangay_id": int(center.barangay_id),
            "latest_ec_update": (
                dict(latest_update)
                if latest_update is not None
                else None
            ),
            "current_allocations": positive_allocations,
        }


def list_current_cross_barangay_allocations(
) -> list[dict[str, object]]:
    with SessionLocal() as session:
        try:
            event_id = _active_event_id(session)
        except CrossBarangayValidationError:
            return []

        return [
            dict(row)
            for row in fetch_latest_cross_allocations_for_event(
                session,
                event_id=event_id,
            )
            if (
                int(row["families"]) > 0
                or int(row["individuals"]) > 0
            )
        ]


def create_cross_barangay_allocation(
    *,
    center_id: int,
    origin_barangay_id: int,
    families: int,
    individuals: int,
    source: str,
    remarks: str | None,
    submission_key: str,
    actor_user_id: int,
) -> int:
    cleaned_source = source.strip()

    if center_id <= 0 or origin_barangay_id <= 0:
        raise CrossBarangayValidationError(
            "A valid center and origin barangay are required."
        )

    if not cleaned_source:
        raise CrossBarangayValidationError(
            "Information source is required."
        )

    canonical_key = _canonical_submission_key(
        submission_key
    )

    with session_scope() as session:
        actor = _require_manager(
            session,
            user_id=actor_user_id,
        )
        event_id = _active_event_id(session)

        if fetch_cross_allocation_by_submission_key(
            session,
            submission_key=canonical_key,
        ) is not None:
            raise DuplicateCrossBarangaySubmissionError(
                "This allocation was already saved. "
                "The duplicate submission was ignored."
            )

        center = fetch_evacuation_center_by_id(
            session,
            center_id=center_id,
        )
        if center is None:
            raise CrossBarangayValidationError(
                "The selected evacuation center does not exist or is inactive."
            )

        origin = fetch_barangay_by_id(
            session,
            origin_barangay_id,
        )
        if origin is None:
            raise CrossBarangayValidationError(
                "The selected origin barangay does not exist or is inactive."
            )

        if int(center.barangay_id) == int(origin.id):
            raise CrossBarangayValidationError(
                "Cross-barangay allocation is only for evacuees whose "
                "home barangay differs from the center's barangay."
            )

        latest_update = fetch_latest_evacuation_update_for_center(
            session,
            event_id=event_id,
            center_id=center_id,
            included_statuses=USABLE_EC_STATUSES,
        )
        if latest_update is None:
            raise CrossBarangayValidationError(
                "Record an evacuation-center occupancy update before "
                "creating a cross-barangay allocation."
            )

        current = fetch_latest_cross_allocations_for_center(
            session,
            event_id=event_id,
            center_id=center_id,
        )

        other_rows = [
            row
            for row in current
            if int(row["origin_barangay_id"]) != origin_barangay_id
        ]

        other_families = sum(
            int(row["families"])
            for row in other_rows
        )
        other_individuals = sum(
            int(row["individuals"])
            for row in other_rows
        )

        validate_cross_allocation(
            families=families,
            individuals=individuals,
            other_families=other_families,
            other_individuals=other_individuals,
            center_families=int(
                latest_update["families"]
            ),
            center_individuals=int(
                latest_update["individuals"]
            ),
        )

        allocation = CrossBarangayEvacuationAllocation(
            event_id=event_id,
            evacuation_center_id=center_id,
            origin_barangay_id=origin_barangay_id,
            submission_key=canonical_key,
            families=families,
            individuals=individuals,
            source=cleaned_source,
            remarks=(
                remarks.strip()
                if remarks and remarks.strip()
                else None
            ),
            recorded_by_user_id=actor.id,
            recorded_by=(
                f"{actor.display_name} — {actor.role}"
            ),
        )

        session.add(allocation)
        session.flush()

        return int(allocation.id)
