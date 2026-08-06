from datetime import datetime

from database.connection import SessionLocal, session_scope
from database.models import AlertLevelHistory, DisasterEvent
from database.repositories import (
    fetch_active_event_rows,
    fetch_alert_level_by_code,
    fetch_alert_levels,
)


class EventServiceError(Exception):
    """Base exception for event-service errors."""


class EventValidationError(EventServiceError):
    """Raised when submitted event information is invalid."""


class ActiveEventAlreadyExistsError(EventServiceError):
    """Raised when an active event already exists."""


class EventDataIntegrityError(EventServiceError):
    """Raised when inconsistent event data is detected."""


def list_alert_levels() -> list[dict[str, object]]:
    """
    Return alert levels that can be displayed in the form.
    """
    with SessionLocal() as session:
        rows = fetch_alert_levels(session)

        return [
            dict(row)
            for row in rows
        ]


def get_active_event_summary() -> dict[str, object] | None:
    """
    Return the current active event, or None when there is none.
    """
    with SessionLocal() as session:
        rows = fetch_active_event_rows(session)

        if len(rows) > 1:
            raise EventDataIntegrityError(
                "More than one active disaster event exists. "
                "Correct the database before continuing."
            )

        if not rows:
            return None

        return dict(rows[0])


def create_event(
    *,
    event_name: str,
    hazard_type: str,
    alert_code: str,
    eoc_status: str,
    started_at: datetime,
    current_sitrep_number: str | None,
    official_reference: str | None,
    situation_overview: str | None,
    initial_alert_reason: str,
    authority_reference: str | None,
) -> int:
    """
    Create one active disaster event and its initial
    alert-level history record.

    Returns the new event ID.
    """
    cleaned_event_name = event_name.strip()
    cleaned_hazard_type = hazard_type.strip()
    cleaned_alert_code = alert_code.strip().upper()
    cleaned_eoc_status = eoc_status.strip()
    cleaned_alert_reason = initial_alert_reason.strip()

    if not cleaned_event_name:
        raise EventValidationError(
            "Event name is required."
        )

    if not cleaned_hazard_type:
        raise EventValidationError(
            "Hazard type is required."
        )

    if not cleaned_alert_code:
        raise EventValidationError(
            "Alert level is required."
        )

    if not cleaned_eoc_status:
        raise EventValidationError(
            "EOC status is required."
        )

    if not cleaned_alert_reason:
        raise EventValidationError(
            "Reason for the initial alert level is required."
        )

    if started_at.tzinfo is None:
        raise EventValidationError(
            "The event start date and time must include "
            "the application timezone."
        )

    with session_scope() as session:
        active_events = fetch_active_event_rows(session)

        if active_events:
            raise ActiveEventAlreadyExistsError(
                "An active disaster event already exists. "
                "Close the current event before creating another."
            )

        alert_level = fetch_alert_level_by_code(
            session,
            cleaned_alert_code,
        )

        if alert_level is None:
            raise EventValidationError(
                f"Alert level '{cleaned_alert_code}' "
                "does not exist in the database."
            )

        event = DisasterEvent(
            event_name=cleaned_event_name,
            hazard_type=cleaned_hazard_type,
            current_alert_level_id=alert_level.id,
            eoc_status=cleaned_eoc_status,
            current_sitrep_number=(
                current_sitrep_number.strip()
                if current_sitrep_number
                and current_sitrep_number.strip()
                else None
            ),
            official_reference=(
                official_reference.strip()
                if official_reference
                and official_reference.strip()
                else None
            ),
            situation_overview=(
                situation_overview.strip()
                if situation_overview
                and situation_overview.strip()
                else None
            ),
            started_at=started_at,
            is_active=True,
        )

        session.add(event)

        # Send the INSERT to PostgreSQL so event.id is assigned.
        session.flush()

        history = AlertLevelHistory(
            event_id=event.id,
            previous_alert_level_id=None,
            new_alert_level_id=alert_level.id,
            effective_at=started_at,
            reason=cleaned_alert_reason,
            authority_reference=(
                authority_reference.strip()
                if authority_reference
                and authority_reference.strip()
                else None
            ),
        )

        session.add(history)
        session.flush()

        return event.id