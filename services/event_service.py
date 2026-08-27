from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from config.access_control import (
    PERMISSION_MANAGE_EVENTS,
    ROLE_ADMINISTRATOR,
    permissions_for_role,
)
from config.constants import (
    TROPICAL_CYCLONE_CLASSIFICATIONS,
)
from database.connection import SessionLocal, session_scope
from database.models import AlertLevelHistory, DisasterEvent, EventChangeHistory, HazardCategory, EOCAlertLevel, \
    EOCStatus
from database.repositories import (
    fetch_active_event_rows,
    fetch_alert_level_by_code,
    fetch_alert_levels,
    fetch_app_user_by_id,
    fetch_event_by_id,
    fetch_event_change_history,
    fetch_recent_events,
)

MANILA_TIMEZONE = ZoneInfo("Asia/Manila")


class EventServiceError(Exception):
    """Base exception for event-service errors."""


class EventValidationError(EventServiceError):
    """Raised when submitted event information is invalid."""


class EventAuthorizationError(EventServiceError):
    """Raised when the authenticated account cannot manage events."""


class ActiveEventAlreadyExistsError(EventServiceError):
    """Raised when an active event already exists."""


class EventDataIntegrityError(EventServiceError):
    """Raised when inconsistent event data is detected."""


class EventStateError(EventServiceError):
    """Raised when an event transition is not allowed."""


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _validate_aware_datetime(value: datetime, label: str) -> None:
    if value.tzinfo is None:
        raise EventValidationError(
            f"{label} must include the application timezone."
        )


def _validate_classification(
        *,
        hazard_type: str,
        classification: str | None,
) -> str | None:
    cleaned = _clean_optional(classification)

    if hazard_type == "Tropical Cyclone":
        if cleaned not in TROPICAL_CYCLONE_CLASSIFICATIONS:
            raise EventValidationError(
                "Select a valid tropical-cyclone classification."
            )
        return cleaned

    return None


def _validate_event_name(
        *,
        event_name: str,
        hazard_type: str,
) -> None:
    if hazard_type != "Tropical Cyclone":
        return

    normalized_name = event_name.casefold()

    for classification in TROPICAL_CYCLONE_CLASSIFICATIONS:
        prefix = classification.casefold() + " "

        if normalized_name.startswith(prefix):
            raise EventValidationError(
                "For a tropical cyclone, enter the event name only "
                "(for example: Luis). Select Tropical Depression, "
                "Tropical Storm, Typhoon, and other classifications "
                "in the separate classification field."
            )


def _require_manager(
        session,
        *,
        user_id: int,
        administrator_only: bool = False,
):
    user = fetch_app_user_by_id(session, user_id=user_id)
    if user is None or not user.is_active:
        raise EventAuthorizationError(
            "Your application account is not active."
        )

    if PERMISSION_MANAGE_EVENTS not in permissions_for_role(user.role):
        raise EventAuthorizationError(
            "Your account is not authorized to manage disaster events."
        )

    if administrator_only and user.role != ROLE_ADMINISTRATOR:
        raise EventAuthorizationError(
            "Only an Administrator may reopen a closed event."
        )

    return user


def _actor_snapshot(user) -> str:
    return f"{user.display_name} — {user.role}"


def _add_history(
        session,
        *,
        event_id: int,
        change_type: str,
        field_name: str,
        previous_value: object | None,
        new_value: object | None,
        reason: str,
        authority_reference: str | None,
        actor,
        effective_at: datetime,
) -> None:
    session.add(
        EventChangeHistory(
            event_id=event_id,
            change_type=change_type,
            field_name=field_name,
            previous_value=(
                None if previous_value is None else str(previous_value)
            ),
            new_value=None if new_value is None else str(new_value),
            reason=reason,
            authority_reference=_clean_optional(authority_reference),
            changed_by_user_id=actor.id,
            changed_by=_actor_snapshot(actor),
            effective_at=effective_at,
        )
    )


def list_alert_levels() -> list[dict[str, object]]:
    with SessionLocal() as session:
        return [dict(row) for row in fetch_alert_levels(session)]


def get_active_event_summary() -> dict[str, object] | None:
    with SessionLocal() as session:
        rows = fetch_active_event_rows(session)
        if len(rows) > 1:
            raise EventDataIntegrityError(
                "More than one active disaster event exists."
            )
        if not rows:
            return None

        row_dict = dict(rows[0])
        if "hazard_category" in row_dict and hasattr(row_dict["hazard_category"], "value"):
            row_dict["hazard_category"] = row_dict["hazard_category"].value
        if "eoc_status" in row_dict and hasattr(row_dict["eoc_status"], "value"):
            row_dict["eoc_status"] = row_dict["eoc_status"].value

        return row_dict


def list_recent_events(*, limit: int = 20) -> list[dict[str, object]]:
    with SessionLocal() as session:
        events = []
        for row in fetch_recent_events(session, limit=limit):
            row_dict = dict(row)
            if "hazard_category" in row_dict and hasattr(row_dict["hazard_category"], "value"):
                row_dict["hazard_category"] = row_dict["hazard_category"].value
            if "eoc_status" in row_dict and hasattr(row_dict["eoc_status"], "value"):
                row_dict["eoc_status"] = row_dict["eoc_status"].value
            events.append(row_dict)
        return events


def get_event_history(
        *,
        event_id: int,
        limit: int = 100,
) -> list[dict[str, object]]:
    with SessionLocal() as session:
        return [
            dict(row)
            for row in fetch_event_change_history(
                session,
                event_id=event_id,
                limit=limit,
            )
        ]


def create_event(
        *,
        event_name: str,
        hazard_category: str,
        hazard_type: str,
        classification: str | None,
        alert_code: str,
        eoc_status: str,
        listo_cpa_level: str | None = None,
        started_at: datetime,
        current_sitrep_number: str | None,
        official_reference: str | None,
        situation_overview: str | None,
        initial_alert_reason: str,
        authority_reference: str | None,
        actor_user_id: int,
) -> int:
    cleaned_name = event_name.strip()
    cleaned_category = hazard_category.strip()
    cleaned_hazard = hazard_type.strip()
    cleaned_alert = alert_code.strip().upper()
    cleaned_eoc = eoc_status.strip()
    cleaned_reason = initial_alert_reason.strip()

    if not cleaned_name:
        raise EventValidationError("Event name is required.")
    if not cleaned_category:
        raise EventValidationError("Hazard category is required.")
    if not cleaned_hazard:
        raise EventValidationError("Hazard type is required.")
    if not cleaned_reason:
        raise EventValidationError(
            "Reason for the initial alert level is required."
        )

    try:
        mapped_category = HazardCategory(cleaned_category)
    except ValueError:
        raise EventValidationError(f"Invalid hazard category: {cleaned_category}")

    try:
        mapped_eoc = EOCStatus(cleaned_eoc)
    except ValueError:
        raise EventValidationError(f"Invalid EOC status: {cleaned_eoc}")

    try:
        mapped_alert = EOCAlertLevel(cleaned_alert)
    except ValueError:
        raise EventValidationError(f"Invalid Alert Level: {cleaned_alert}")

    _validate_event_name(
        event_name=cleaned_name,
        hazard_type=cleaned_hazard,
    )

    _validate_aware_datetime(started_at, "Event start date and time")
    cleaned_classification = _validate_classification(
        hazard_type=cleaned_hazard,
        classification=classification,
    )

    try:
        with session_scope() as session:
            actor = _require_manager(session, user_id=actor_user_id)

            if fetch_active_event_rows(session):
                raise ActiveEventAlreadyExistsError(
                    "An active disaster event already exists. Close it before "
                    "creating another event."
                )

            alert_level = fetch_alert_level_by_code(session, mapped_alert.value)
            if alert_level is None:
                raise EventValidationError(
                    f"Alert level '{mapped_alert.value}' does not exist in registry."
                )

            event = DisasterEvent(
                event_name=cleaned_name,
                hazard_category=mapped_category,
                hazard_type=cleaned_hazard,
                classification=cleaned_classification,
                listo_cpa_level=_clean_optional(listo_cpa_level),
                current_alert_level_id=alert_level.id,
                eoc_status=mapped_eoc,
                current_sitrep_number=_clean_optional(current_sitrep_number),
                official_reference=_clean_optional(official_reference),
                situation_overview=_clean_optional(situation_overview),
                started_at=started_at,
                is_active=True,
            )
            session.add(event)
            session.flush()

            session.add(
                AlertLevelHistory(
                    event_id=event.id,
                    previous_alert_level_id=None,
                    new_alert_level_id=alert_level.id,
                    effective_at=started_at,
                    reason=cleaned_reason,
                    authority_reference=_clean_optional(authority_reference),
                    changed_by_user_id=actor.id,
                    changed_by=_actor_snapshot(actor),
                )
            )

            _add_history(
                session,
                event_id=event.id,
                change_type="Created",
                field_name="event",
                previous_value=None,
                new_value=(
                    f"{cleaned_classification} {cleaned_name}"
                    if cleaned_classification
                    else cleaned_name
                ),
                reason=cleaned_reason,
                authority_reference=authority_reference,
                actor=actor,
                effective_at=started_at,
            )

            session.flush()
            return int(event.id)

    except IntegrityError as error:
        if "uq_disaster_events_one_active" in str(error.orig):
            raise ActiveEventAlreadyExistsError(
                "Another active event already exists."
            ) from error
        raise


def update_event_details(
        *,
        event_id: int,
        event_name: str,
        classification: str | None,
        current_sitrep_number: str | None,
        official_reference: str | None,
        situation_overview: str | None,
        reason: str,
        authority_reference: str | None,
        actor_user_id: int,
) -> None:
    cleaned_name = event_name.strip()
    cleaned_reason = reason.strip()

    if not cleaned_name:
        raise EventValidationError("Event name is required.")
    if not cleaned_reason:
        raise EventValidationError("Reason for the change is required.")

    now = datetime.now(MANILA_TIMEZONE)

    with session_scope() as session:
        actor = _require_manager(session, user_id=actor_user_id)
        event = fetch_event_by_id(
            session,
            event_id=event_id,
            for_update=True,
        )

        if event is None:
            raise EventValidationError("The selected event does not exist.")
        if not event.is_active:
            raise EventStateError("Only the active event may be edited.")

        _validate_event_name(
            event_name=cleaned_name,
            hazard_type=event.hazard_type,
        )

        new_classification = _validate_classification(
            hazard_type=event.hazard_type,
            classification=classification,
        )

        new_values = {
            "event_name": cleaned_name,
            "classification": new_classification,
            "current_sitrep_number": _clean_optional(current_sitrep_number),
            "official_reference": _clean_optional(official_reference),
            "situation_overview": _clean_optional(situation_overview),
        }

        changes = []
        for field_name, new_value in new_values.items():
            old_value = getattr(event, field_name)
            if old_value != new_value:
                changes.append((field_name, old_value, new_value))

        if not changes:
            raise EventValidationError("No event-detail changes were detected.")

        for field_name, old_value, new_value in changes:
            setattr(event, field_name, new_value)
            _add_history(
                session,
                event_id=event.id,
                change_type="Updated",
                field_name=field_name,
                previous_value=old_value,
                new_value=new_value,
                reason=cleaned_reason,
                authority_reference=authority_reference,
                actor=actor,
                effective_at=now,
            )

        session.flush()


def change_event_alert(
        *,
        event_id: int,
        new_alert_code: str,
        effective_at: datetime,
        reason: str,
        authority_reference: str | None,
        actor_user_id: int,
) -> None:
    cleaned_reason = reason.strip()

    if not cleaned_reason:
        raise EventValidationError("Reason for the alert change is required.")

    _validate_aware_datetime(
        effective_at,
        "Alert effective date and time",
    )

    try:
        mapped_alert = EOCAlertLevel(new_alert_code.strip().upper())
    except ValueError:
        raise EventValidationError(f"Invalid strict Alert Level Enum: {new_alert_code}")

    with session_scope() as session:
        actor = _require_manager(session, user_id=actor_user_id)
        event = fetch_event_by_id(
            session,
            event_id=event_id,
            for_update=True,
        )

        if event is None or not event.is_active:
            raise EventStateError("The event is not active.")

        new_level = fetch_alert_level_by_code(
            session,
            mapped_alert.value,
        )

        if new_level is None:
            raise EventValidationError(
                "The selected alert level is invalid."
            )

        if int(new_level.id) == int(event.current_alert_level_id):
            raise EventValidationError(
                "The selected alert level is already in effect."
            )

        old_level_id = int(event.current_alert_level_id)
        old_level = next(
            (
                row
                for row in fetch_alert_levels(session)
                if int(row["id"]) == old_level_id
            ),
            None,
        )
        old_code = (
            str(old_level["code"])
            if old_level
            else str(old_level_id)
        )

        event.current_alert_level_id = new_level.id

        session.add(
            AlertLevelHistory(
                event_id=event.id,
                previous_alert_level_id=old_level_id,
                new_alert_level_id=new_level.id,
                effective_at=effective_at,
                reason=cleaned_reason,
                authority_reference=_clean_optional(authority_reference),
                changed_by_user_id=actor.id,
                changed_by=_actor_snapshot(actor),
            )
        )

        _add_history(
            session,
            event_id=event.id,
            change_type="Alert Change",
            field_name="alert_level",
            previous_value=old_code,
            new_value=new_level.code,
            reason=cleaned_reason,
            authority_reference=authority_reference,
            actor=actor,
            effective_at=effective_at,
        )

        session.flush()


def change_eoc_status(
        *,
        event_id: int,
        new_status: str,
        reason: str,
        authority_reference: str | None,
        actor_user_id: int,
) -> None:
    cleaned_status = new_status.strip()
    cleaned_reason = reason.strip()

    if not cleaned_reason:
        raise EventValidationError(
            "Reason for the EOC change is required."
        )

    try:
        mapped_eoc = EOCStatus(cleaned_status)
    except ValueError:
        raise EventValidationError(f"Invalid EOC status Enum: {cleaned_status}")

    now = datetime.now(MANILA_TIMEZONE)

    with session_scope() as session:
        actor = _require_manager(session, user_id=actor_user_id)
        event = fetch_event_by_id(
            session,
            event_id=event_id,
            for_update=True,
        )

        if event is None or not event.is_active:
            raise EventStateError("The event is not active.")

        if event.eoc_status == mapped_eoc:
            raise EventValidationError(
                "The selected EOC status is already in effect."
            )

        old_status = event.eoc_status.value if hasattr(event.eoc_status, "value") else str(event.eoc_status)
        event.eoc_status = mapped_eoc

        _add_history(
            session,
            event_id=event.id,
            change_type="EOC Change",
            field_name="eoc_status",
            previous_value=old_status,
            new_value=mapped_eoc.value,
            reason=cleaned_reason,
            authority_reference=authority_reference,
            actor=actor,
            effective_at=now,
        )

        session.flush()


def close_event(
        *,
        event_id: int,
        ended_at: datetime,
        reason: str,
        authority_reference: str | None,
        actor_user_id: int,
) -> None:
    cleaned_reason = reason.strip()

    if not cleaned_reason:
        raise EventValidationError(
            "Reason for closing the event is required."
        )

    _validate_aware_datetime(
        ended_at,
        "Event end date and time",
    )

    with session_scope() as session:
        actor = _require_manager(session, user_id=actor_user_id)
        event = fetch_event_by_id(
            session,
            event_id=event_id,
            for_update=True,
        )

        if event is None or not event.is_active:
            raise EventStateError("The event is not active.")

        if ended_at < event.started_at:
            raise EventValidationError(
                "Event end time cannot be earlier than its start time."
            )

        old_eoc_value = event.eoc_status.value if hasattr(event.eoc_status, "value") else str(event.eoc_status)

        # Standard practice: Demote to Monitoring upon closure if active
        if old_eoc_value != EOCStatus.MONITORING.value:
            event.eoc_status = EOCStatus.MONITORING

            _add_history(
                session,
                event_id=event.id,
                change_type="EOC Change",
                field_name="eoc_status",
                previous_value=old_eoc_value,
                new_value=EOCStatus.MONITORING.value,
                reason=cleaned_reason,
                authority_reference=authority_reference,
                actor=actor,
                effective_at=ended_at,
            )

        event.ended_at = ended_at
        event.is_active = False

        _add_history(
            session,
            event_id=event.id,
            change_type="Closed",
            field_name="lifecycle",
            previous_value="Active",
            new_value="Closed",
            reason=cleaned_reason,
            authority_reference=authority_reference,
            actor=actor,
            effective_at=ended_at,
        )

        session.flush()


def reopen_event(
        *,
        event_id: int,
        reason: str,
        authority_reference: str | None,
        actor_user_id: int,
) -> None:
    cleaned_reason = reason.strip()

    if not cleaned_reason:
        raise EventValidationError(
            "Reason for reopening the event is required."
        )

    now = datetime.now(MANILA_TIMEZONE)

    try:
        with session_scope() as session:
            actor = _require_manager(
                session,
                user_id=actor_user_id,
                administrator_only=True,
            )

            if fetch_active_event_rows(session):
                raise ActiveEventAlreadyExistsError(
                    "Close the current active event before reopening another."
                )

            event = fetch_event_by_id(
                session,
                event_id=event_id,
                for_update=True,
            )

            if event is None:
                raise EventValidationError(
                    "The selected event does not exist."
                )

            if event.is_active:
                raise EventStateError(
                    "The selected event is already active."
                )

            old_eoc_value = event.eoc_status.value if hasattr(event.eoc_status, "value") else str(event.eoc_status)

            event.is_active = True
            event.ended_at = None
            event.eoc_status = EOCStatus.MONITORING

            _add_history(
                session,
                event_id=event.id,
                change_type="Reopened",
                field_name="lifecycle",
                previous_value="Closed",
                new_value="Active",
                reason=cleaned_reason,
                authority_reference=authority_reference,
                actor=actor,
                effective_at=now,
            )

            if old_eoc_value != EOCStatus.MONITORING.value:
                _add_history(
                    session,
                    event_id=event.id,
                    change_type="EOC Change",
                    field_name="eoc_status",
                    previous_value=old_eoc_value,
                    new_value=EOCStatus.MONITORING.value,
                    reason=cleaned_reason,
                    authority_reference=authority_reference,
                    actor=actor,
                    effective_at=now,
                )

            session.flush()

    except IntegrityError as error:
        if "uq_disaster_events_one_active" in str(error.orig):
            raise ActiveEventAlreadyExistsError(
                "Another event became active before this event could reopen."
            ) from error
        raise