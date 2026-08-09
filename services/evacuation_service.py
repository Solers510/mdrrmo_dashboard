from sqlalchemy.exc import IntegrityError
from services.audit_context import set_audit_actor

from config.access_control import (
    PERMISSION_MANAGE_EVACUATION_CENTERS,
    PERMISSION_SUBMIT_EVACUATION_UPDATES,
    permissions_for_role,
)
from database.connection import SessionLocal, session_scope
from database.models import (
    EvacuationCenter,
    EvacuationCenterUpdate,
)
from database.repositories import (
    fetch_active_event_rows,
    fetch_active_evacuation_centers,
    fetch_app_user_by_id,
    fetch_barangay_by_id,
    fetch_evacuation_center_by_id,
    fetch_evacuation_center_by_name_barangay,
    fetch_evacuation_update_by_submission_key,
    fetch_needs_correction_evacuation_updates,
    fetch_recent_evacuation_center_updates,
)
from services.data_integrity import (
    DataIntegrityValidationError,
    validate_evacuation_occupancy,
    validate_submission_key,
)


class EvacuationServiceError(Exception):
    """Base evacuation-center service exception."""


class EvacuationValidationError(
    EvacuationServiceError
):
    """Raised when submitted values are invalid."""


class EvacuationAuthorizationError(
    EvacuationServiceError
):
    """Raised when the account lacks permission."""


class EvacuationDataIntegrityError(
    EvacuationServiceError
):
    """Raised when inconsistent records are detected."""


class DuplicateEvacuationSubmissionError(
    EvacuationServiceError
):
    """Raised when the same occupancy form is submitted twice."""


class NoActiveEventError(
    EvacuationServiceError
):
    """Raised when no active disaster event exists."""


def _require_permission(
    session,
    *,
    user_id: int,
    permission: str,
):
    user = fetch_app_user_by_id(
        session,
        user_id=user_id,
    )

    if user is None or not user.is_active:
        raise EvacuationAuthorizationError(
            "Your application account is not active."
        )

    if permission not in permissions_for_role(
        user.role
    ):
        raise EvacuationAuthorizationError(
            "Your account is not authorized "
            "to perform this action."
        )

    set_audit_actor(
        session,
        user_id=int(user.id),
        display_name=str(user.display_name),
        role=str(user.role),
    )

    return user
def list_active_evacuation_centers(
) -> list[dict[str, object]]:
    try:
        with SessionLocal() as session:
            return [
                dict(row)
                for row
                in fetch_active_evacuation_centers(
                    session
                )
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
    actor_user_id: int,
) -> int:
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
        _require_permission(
            session,
            user_id=actor_user_id,
            permission=(
                PERMISSION_MANAGE_EVACUATION_CENTERS
            ),
        )

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

        return int(center.id)


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
    submission_key: str,
    submitter_user_id: int,
) -> int:
    cleaned_source = source.strip()
    cleaned_sanitation = (
        sanitation_status.strip()
    )

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

    try:
        canonical_key = validate_submission_key(
            submission_key
        )
    except DataIntegrityValidationError as error:
        raise EvacuationValidationError(
            str(error)
        ) from error

    try:
        with session_scope() as session:
            submitter = _require_permission(
                session,
                user_id=submitter_user_id,
                permission=(
                    PERMISSION_SUBMIT_EVACUATION_UPDATES
                ),
            )

            duplicate = (
                fetch_evacuation_update_by_submission_key(
                    session,
                    submission_key=canonical_key,
                )
            )

            if duplicate is not None:
                raise (
                    DuplicateEvacuationSubmissionError(
                        "This evacuation report was "
                        "already saved. The duplicate "
                        "submission was ignored."
                    )
                )

            active_events = fetch_active_event_rows(
                session
            )

            if len(active_events) > 1:
                raise EvacuationDataIntegrityError(
                    "More than one active disaster "
                    "event exists."
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
                    "The selected evacuation center "
                    "does not exist or is inactive."
                )

            try:
                validate_evacuation_occupancy(
                    status=status,
                    families=families,
                    individuals=individuals,
                    children=children,
                    senior_citizens=senior_citizens,
                    pwd=pwd,
                    pregnant_women=pregnant_women,
                    medical_cases=medical_cases,
                    safe_capacity=int(
                        center.safe_capacity
                    ),
                )
            except (
                DataIntegrityValidationError
            ) as error:
                raise EvacuationValidationError(
                    str(error)
                ) from error

            event_id = int(
                active_events[0]["id"]
            )

            correction_reports = (
                fetch_needs_correction_evacuation_updates(
                    session,
                    event_id=event_id,
                    center_id=int(center.id),
                )
            )

            supersedes_update_id = (
                int(correction_reports[0].id)
                if correction_reports
                else None
            )

            update = EvacuationCenterUpdate(
                event_id=event_id,
                evacuation_center_id=center.id,
                supersedes_update_id=supersedes_update_id,
                submission_key=canonical_key,
                submitted_by_user_id=(
                    submitter.id
                ),
                submitted_by=(
                    f"{submitter.display_name} — "
                    f"{submitter.role}"
                ),
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
                electricity_status=(
                    electricity_status
                ),
                sanitation_status=cleaned_sanitation,
                source=cleaned_source,
                validation_status="Submitted",
                remarks=(
                    remarks.strip()
                    if remarks and remarks.strip()
                    else None
                ),
            )

            for previous_report in correction_reports:
                previous_report.validation_status = "Superseded"

            session.add(update)
            session.flush()

            return int(update.id)

    except IntegrityError as error:
        if (
            "uq_evacuation_updates_submission_key"
            in str(error.orig)
        ):
            raise (
                DuplicateEvacuationSubmissionError(
                    "This evacuation report was already "
                    "saved. The duplicate submission "
                    "was ignored."
                )
            ) from error
        raise


def get_recent_evacuation_updates(
    *,
    limit: int = 20,
) -> list[dict[str, object]]:
    with SessionLocal() as session:
        active_events = fetch_active_event_rows(
            session
        )

        if len(active_events) > 1:
            raise EvacuationDataIntegrityError(
                "More than one active disaster "
                "event exists."
            )

        if not active_events:
            return []

        rows = fetch_recent_evacuation_center_updates(
            session,
            event_id=int(
                active_events[0]["id"]
            ),
            limit=limit,
        )

        return [
            dict(row)
            for row in rows
        ]
