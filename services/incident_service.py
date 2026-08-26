from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from config.access_control import (
    PERMISSION_MANAGE_INCIDENTS,
    ROLE_ADMINISTRATOR,
    permissions_for_role,
)
from database.connection import SessionLocal, session_scope
from database.models import (
    Incident,
    IncidentHistory,
)
from database.repositories import (
    fetch_active_event_rows,
    fetch_app_user_by_id,
    fetch_barangay_by_id,
    fetch_incident_active_assignments,
    fetch_incident_by_id,
    fetch_incident_by_submission_key,
    fetch_incident_history,
    fetch_recent_incidents,
)
from services.data_integrity import (
    DataIntegrityValidationError,
    validate_submission_key,
)


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

INCIDENT_TYPES = (
    "Flooding",
    "Rescue Request",
    "Medical Emergency",
    "Fallen Tree",
    "Road Obstruction",
    "Structural Damage",
    "Power Interruption",
    "Water Interruption",
    "Landslide",
    "Maritime Incident",
    "Missing Person",
    "Fire",
    "Other",
)

INCIDENT_PRIORITIES = (
    "Low",
    "Moderate",
    "High",
    "Critical",
)

INCIDENT_STATUSES = (
    "Reported",
    "For Verification",
    "Verified",
    "Team Dispatched",
    "Responding",
    "Resolved",
    "Cancelled",
)

_STATUS_RANK = {
    "Reported": 0,
    "For Verification": 1,
    "Verified": 2,
    "Team Dispatched": 3,
    "Responding": 4,
    "Resolved": 5,
}

TERMINAL_INCIDENT_STATUSES = {
    "Resolved",
    "Cancelled",
}


class IncidentServiceError(Exception):
    """Base exception for incident operations."""


class IncidentValidationError(IncidentServiceError):
    """Raised when incident information is invalid."""


class IncidentAuthorizationError(IncidentServiceError):
    """Raised when the account cannot manage incidents."""


class IncidentDataIntegrityError(IncidentServiceError):
    """Raised when database state is inconsistent."""


class IncidentStateError(IncidentServiceError):
    """Raised when an incident transition is not allowed."""


class DuplicateIncidentSubmissionError(IncidentServiceError):
    """Raised when the same incident form is submitted twice."""


class NoActiveEventError(IncidentServiceError):
    """Raised when no active disaster event exists."""


def allowed_incident_transitions(
    current_status: str,
) -> tuple[str, ...]:
    """
    Return forward operational transitions.

    Steps may be skipped when urgent operations require it, but normal
    workflow cannot move backward. Resolved/Cancelled are terminal.
    """
    if current_status in TERMINAL_INCIDENT_STATUSES:
        return ()

    if current_status not in _STATUS_RANK:
        return ()

    current_rank = _STATUS_RANK[current_status]

    forward = [
        status
        for status, rank in _STATUS_RANK.items()
        if rank > current_rank
    ]

    return tuple(forward + ["Cancelled"])


def _active_event_id(session) -> int:
    rows = fetch_active_event_rows(session)

    if len(rows) > 1:
        raise IncidentDataIntegrityError(
            "More than one active disaster event exists."
        )

    if not rows:
        raise NoActiveEventError(
            "No active disaster event exists."
        )

    return int(rows[0]["id"])


def _require_manager(
    session,
    *,
    user_id: int,
    administrator_only: bool = False,
):
    user = fetch_app_user_by_id(
        session,
        user_id=user_id,
    )

    if user is None or not user.is_active:
        raise IncidentAuthorizationError(
            "Your application account is not active."
        )

    if (
        PERMISSION_MANAGE_INCIDENTS
        not in permissions_for_role(user.role)
    ):
        raise IncidentAuthorizationError(
            "Your account is not authorized to manage incidents."
        )

    if administrator_only and user.role != ROLE_ADMINISTRATOR:
        raise IncidentAuthorizationError(
            "Only an Administrator may reopen a closed incident."
        )

    return user


def _actor_snapshot(user) -> str:
    return f"{user.display_name} — {user.role}"


def _add_history(
    session,
    *,
    incident_id: int,
    change_type: str,
    field_name: str,
    previous_value: object | None,
    new_value: object | None,
    notes: str,
    actor,
    effective_at: datetime | None = None,
) -> None:
    session.add(
        IncidentHistory(
            incident_id=incident_id,
            change_type=change_type,
            field_name=field_name,
            previous_value=(
                None
                if previous_value is None
                else str(previous_value)
            ),
            new_value=(
                None
                if new_value is None
                else str(new_value)
            ),
            notes=notes,
            changed_by_user_id=actor.id,
            changed_by=_actor_snapshot(actor),
            effective_at=(
                effective_at
                or datetime.now(MANILA_TIMEZONE)
            ),
        )
    )


def create_incident(
    *,
    barangay_id: int,
    exact_location: str,
    incident_type: str,
    description: str,
    priority: str,
    persons_affected: int,
    source: str,
    submission_key: str,
    reporter_user_id: int,
) -> int:
    cleaned_location = exact_location.strip()
    cleaned_description = description.strip()
    cleaned_source = source.strip()

    if barangay_id <= 0:
        raise IncidentValidationError(
            "A valid barangay is required."
        )

    if not cleaned_location:
        raise IncidentValidationError(
            "Exact location or landmark is required."
        )

    if incident_type not in INCIDENT_TYPES:
        raise IncidentValidationError(
            "Select a valid incident type."
        )

    if not cleaned_description:
        raise IncidentValidationError(
            "Incident description is required."
        )

    if priority not in INCIDENT_PRIORITIES:
        raise IncidentValidationError(
            "Select a valid priority."
        )

    if persons_affected < 0:
        raise IncidentValidationError(
            "Persons affected cannot be negative."
        )

    if not cleaned_source:
        raise IncidentValidationError(
            "Information source is required."
        )

    try:
        canonical_key = validate_submission_key(
            submission_key
        )
    except DataIntegrityValidationError as error:
        raise IncidentValidationError(
            str(error)
        ) from error

    try:
        with session_scope() as session:
            reporter = _require_manager(
                session,
                user_id=reporter_user_id,
            )

            if fetch_incident_by_submission_key(
                session,
                submission_key=canonical_key,
            ) is not None:
                raise DuplicateIncidentSubmissionError(
                    "This incident was already saved. "
                    "The duplicate submission was ignored."
                )

            event_id = _active_event_id(session)

            barangay = fetch_barangay_by_id(
                session,
                barangay_id,
            )
            if barangay is None:
                raise IncidentValidationError(
                    "The selected barangay does not exist or is inactive."
                )

            incident = Incident(
                event_id=event_id,
                control_number=(
                    f"TMP-{uuid4().hex[:24].upper()}"
                ),
                submission_key=canonical_key,
                reported_by_user_id=reporter.id,
                reported_by=_actor_snapshot(reporter),
                barangay_id=int(barangay.id),
                exact_location=cleaned_location,
                incident_type=incident_type,
                description=cleaned_description,
                priority=priority,
                persons_affected=persons_affected,
                status="Reported",
                source=cleaned_source,
                validation_status="Submitted",
            )

            session.add(incident)
            session.flush()

            incident.control_number = (
                f"INC-{event_id:04d}-{int(incident.id):05d}"
            )

            _add_history(
                session,
                incident_id=int(incident.id),
                change_type="Created",
                field_name="status",
                previous_value=None,
                new_value="Reported",
                notes=(
                    "Incident created from operational report. "
                    f"Source: {cleaned_source}"
                ),
                actor=reporter,
            )

            session.flush()
            return int(incident.id)

    except IntegrityError as error:
        message = str(error.orig)

        if "uq_incidents_submission_key" in message:
            raise DuplicateIncidentSubmissionError(
                "This incident was already saved. "
                "The duplicate submission was ignored."
            ) from error

        raise


def list_recent_incidents(
    *,
    limit: int = 100,
) -> list[dict[str, object]]:
    with SessionLocal() as session:
        try:
            event_id = _active_event_id(session)
        except NoActiveEventError:
            return []

        return [
            dict(row)
            for row in fetch_recent_incidents(
                session,
                event_id=event_id,
                limit=limit,
            )
        ]


def get_incident_history(
    *,
    incident_id: int,
    limit: int = 100,
) -> list[dict[str, object]]:
    with SessionLocal() as session:
        return [
            dict(row)
            for row in fetch_incident_history(
                session,
                incident_id=incident_id,
                limit=limit,
            )
        ]


def change_incident_status(
    *,
    incident_id: int,
    new_status: str,
    notes: str,
    actor_user_id: int,
) -> None:
    cleaned_notes = notes.strip()

    if not cleaned_notes:
        raise IncidentValidationError(
            "Reason or operational notes are required."
        )

    if new_status not in INCIDENT_STATUSES:
        raise IncidentValidationError(
            "Select a valid incident status."
        )

    now = datetime.now(MANILA_TIMEZONE)

    with session_scope() as session:
        actor = _require_manager(
            session,
            user_id=actor_user_id,
        )
        event_id = _active_event_id(session)

        incident = fetch_incident_by_id(
            session,
            incident_id=incident_id,
            for_update=True,
        )

        if incident is None:
            raise IncidentValidationError(
                "The selected incident does not exist."
            )

        if int(incident.event_id) != event_id:
            raise IncidentStateError(
                "The selected incident does not belong to the active event."
            )

        allowed = allowed_incident_transitions(
            incident.status
        )

        if new_status not in allowed:
            raise IncidentStateError(
                f"Incident status cannot move from "
                f"{incident.status} to {new_status}."
            )

        previous_status = incident.status
        incident.status = new_status
        incident.action_taken = cleaned_notes

        if new_status in {
            "Verified",
            "Team Dispatched",
            "Responding",
            "Resolved",
        }:
            incident.validation_status = "Validated"

        if new_status == "Resolved":
            incident.resolved_at = now

        if new_status in TERMINAL_INCIDENT_STATUSES:
            active_assignments = (
                fetch_incident_active_assignments(
                    session,
                    incident_id=incident_id,
                    for_update=True,
                )
            )

            for assignment, resource in active_assignments:
                assignment.released_at = now
                resource.status = "Available"

                snapshot = (
                    f"{resource.resource_code} — {resource.name}"
                )
                if (
                    resource.resource_type == "Response Team"
                    and incident.assigned_team == snapshot
                ):
                    incident.assigned_team = None
                elif (
                    resource.resource_type == "Vehicle"
                    and incident.assigned_vehicle == snapshot
                ):
                    incident.assigned_vehicle = None

                _add_history(
                    session,
                    incident_id=incident_id,
                    change_type="Resource Released",
                    field_name="resource",
                    previous_value=resource.name,
                    new_value="Available",
                    notes=(
                        "Automatically released because the incident "
                        f"was marked {new_status}."
                    ),
                    actor=actor,
                    effective_at=now,
                )

        _add_history(
            session,
            incident_id=incident_id,
            change_type="Status Change",
            field_name="status",
            previous_value=previous_status,
            new_value=new_status,
            notes=cleaned_notes,
            actor=actor,
            effective_at=now,
        )

        session.flush()


def change_incident_priority(
    *,
    incident_id: int,
    new_priority: str,
    reason: str,
    actor_user_id: int,
) -> None:
    cleaned_reason = reason.strip()

    if new_priority not in INCIDENT_PRIORITIES:
        raise IncidentValidationError(
            "Select a valid priority."
        )

    if not cleaned_reason:
        raise IncidentValidationError(
            "Reason for the priority change is required."
        )

    with session_scope() as session:
        actor = _require_manager(
            session,
            user_id=actor_user_id,
        )
        event_id = _active_event_id(session)

        incident = fetch_incident_by_id(
            session,
            incident_id=incident_id,
            for_update=True,
        )

        if incident is None:
            raise IncidentValidationError(
                "The selected incident does not exist."
            )

        if int(incident.event_id) != event_id:
            raise IncidentStateError(
                "The selected incident does not belong to the active event."
            )

        if incident.priority == new_priority:
            raise IncidentValidationError(
                "The selected priority is already in effect."
            )

        previous = incident.priority
        incident.priority = new_priority

        _add_history(
            session,
            incident_id=incident_id,
            change_type="Priority Change",
            field_name="priority",
            previous_value=previous,
            new_value=new_priority,
            notes=cleaned_reason,
            actor=actor,
        )

        session.flush()


def reopen_incident(
    *,
    incident_id: int,
    reason: str,
    actor_user_id: int,
) -> None:
    cleaned_reason = reason.strip()

    if not cleaned_reason:
        raise IncidentValidationError(
            "Reason for reopening is required."
        )

    with session_scope() as session:
        actor = _require_manager(
            session,
            user_id=actor_user_id,
            administrator_only=True,
        )
        event_id = _active_event_id(session)

        incident = fetch_incident_by_id(
            session,
            incident_id=incident_id,
            for_update=True,
        )

        if incident is None:
            raise IncidentValidationError(
                "The selected incident does not exist."
            )

        if int(incident.event_id) != event_id:
            raise IncidentStateError(
                "Only incidents from the active event may be reopened."
            )

        if incident.status not in TERMINAL_INCIDENT_STATUSES:
            raise IncidentStateError(
                "Only Resolved or Cancelled incidents may be reopened."
            )

        previous = incident.status
        incident.status = "For Verification"
        incident.resolved_at = None
        incident.validation_status = "Submitted"

        _add_history(
            session,
            incident_id=incident_id,
            change_type="Reopened",
            field_name="status",
            previous_value=previous,
            new_value="For Verification",
            notes=cleaned_reason,
            actor=actor,
        )

        session.flush()
