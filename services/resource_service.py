from datetime import datetime
from zoneinfo import ZoneInfo

from config.access_control import (
    PERMISSION_MANAGE_INCIDENTS,
    permissions_for_role,
)
from database.connection import SessionLocal, session_scope
from database.models import (
    IncidentHistory,
    IncidentResourceAssignment,
    ResponseResource,
)
from database.repositories import (
    fetch_active_event_rows,
    fetch_active_resource_assignment,
    fetch_app_user_by_id,
    fetch_assignment_by_id,
    fetch_incident_active_assignments,
    fetch_incident_by_id,
    fetch_resource_by_code,
    fetch_resource_by_id,
    fetch_response_resources,
)


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

RESOURCE_TYPES = (
    "Response Team",
    "Vehicle",
    "Equipment",
)

RESOURCE_STATUSES = (
    "Available",
    "Assigned",
    "Maintenance",
    "Out of Service",
)

MANUAL_RESOURCE_STATUSES = (
    "Available",
    "Maintenance",
    "Out of Service",
)


class ResourceServiceError(Exception):
    """Base exception for response-resource operations."""


class ResourceValidationError(ResourceServiceError):
    """Raised when resource information is invalid."""


class ResourceAuthorizationError(ResourceServiceError):
    """Raised when the account lacks permission."""


class ResourceStateError(ResourceServiceError):
    """Raised when resource state prevents an operation."""


class ResourceDataIntegrityError(ResourceServiceError):
    """Raised when operational data is inconsistent."""


def validate_manual_resource_status(
    *,
    current_status: str,
    new_status: str,
    has_active_assignment: bool,
) -> None:
    if new_status not in MANUAL_RESOURCE_STATUSES:
        raise ResourceValidationError(
            "Assigned status is controlled automatically by dispatch."
        )

    if has_active_assignment:
        raise ResourceStateError(
            "Release the resource from its active incident before "
            "changing readiness status."
        )

    if current_status == new_status:
        raise ResourceValidationError(
            "The selected resource status is already in effect."
        )


def _active_event_id(session) -> int:
    rows = fetch_active_event_rows(session)

    if len(rows) > 1:
        raise ResourceDataIntegrityError(
            "More than one active disaster event exists."
        )

    if not rows:
        raise ResourceStateError(
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
        raise ResourceAuthorizationError(
            "Your application account is not active."
        )

    if (
        PERMISSION_MANAGE_INCIDENTS
        not in permissions_for_role(user.role)
    ):
        raise ResourceAuthorizationError(
            "Your account is not authorized to manage response resources."
        )

    return user


def _snapshot(user) -> str:
    return f"{user.display_name} — {user.role}"


def _add_incident_history(
    session,
    *,
    incident_id: int,
    change_type: str,
    resource_name: str,
    new_value: str,
    notes: str,
    actor,
    effective_at: datetime,
) -> None:
    session.add(
        IncidentHistory(
            incident_id=incident_id,
            change_type=change_type,
            field_name="resource",
            previous_value=resource_name,
            new_value=new_value,
            notes=notes,
            changed_by_user_id=actor.id,
            changed_by=_snapshot(actor),
            effective_at=effective_at,
        )
    )


def list_response_resources() -> list[dict[str, object]]:
    with SessionLocal() as session:
        return [
            dict(row)
            for row in fetch_response_resources(session)
        ]


def create_response_resource(
    *,
    resource_code: str,
    name: str,
    resource_type: str,
    subtype: str | None,
    details: str | None,
    actor_user_id: int,
) -> int:
    cleaned_code = resource_code.strip().upper()
    cleaned_name = name.strip()

    if not cleaned_code:
        raise ResourceValidationError(
            "Resource code is required."
        )

    if not cleaned_name:
        raise ResourceValidationError(
            "Resource name is required."
        )

    if resource_type not in RESOURCE_TYPES:
        raise ResourceValidationError(
            "Select a valid resource type."
        )

    with session_scope() as session:
        _require_manager(
            session,
            user_id=actor_user_id,
        )

        if fetch_resource_by_code(
            session,
            resource_code=cleaned_code,
        ) is not None:
            raise ResourceValidationError(
                "That resource code already exists."
            )

        resource = ResponseResource(
            resource_code=cleaned_code,
            name=cleaned_name,
            resource_type=resource_type,
            subtype=(
                subtype.strip()
                if subtype and subtype.strip()
                else None
            ),
            details=(
                details.strip()
                if details and details.strip()
                else None
            ),
            status="Available",
            is_active=True,
        )

        session.add(resource)
        session.flush()
        return int(resource.id)


def set_resource_status(
    *,
    resource_id: int,
    new_status: str,
    actor_user_id: int,
) -> None:
    with session_scope() as session:
        _require_manager(
            session,
            user_id=actor_user_id,
        )

        resource = fetch_resource_by_id(
            session,
            resource_id=resource_id,
            for_update=True,
        )

        if resource is None or not resource.is_active:
            raise ResourceValidationError(
                "The selected resource does not exist or is inactive."
            )

        assignment = fetch_active_resource_assignment(
            session,
            resource_id=resource_id,
            for_update=True,
        )

        validate_manual_resource_status(
            current_status=resource.status,
            new_status=new_status,
            has_active_assignment=assignment is not None,
        )

        resource.status = new_status
        session.flush()


def list_incident_assignments(
    *,
    incident_id: int,
) -> list[dict[str, object]]:
    with SessionLocal() as session:
        rows = fetch_incident_active_assignments(
            session,
            incident_id=incident_id,
            for_update=False,
        )

        return [
            {
                "assignment_id": int(assignment.id),
                "resource_id": int(resource.id),
                "resource_code": resource.resource_code,
                "resource_name": resource.name,
                "resource_type": resource.resource_type,
                "subtype": resource.subtype,
                "assigned_at": assignment.assigned_at,
                "notes": assignment.notes,
                "assigned_by": assignment.assigned_by,
            }
            for assignment, resource in rows
        ]


def assign_resource_to_incident(
    *,
    incident_id: int,
    resource_id: int,
    notes: str | None,
    actor_user_id: int,
) -> int:
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
            raise ResourceValidationError(
                "The selected incident does not exist."
            )

        if int(incident.event_id) != event_id:
            raise ResourceStateError(
                "The selected incident does not belong to the active event."
            )

        if incident.status in {"Resolved", "Cancelled"}:
            raise ResourceStateError(
                "Resources cannot be assigned to a closed incident."
            )

        resource = fetch_resource_by_id(
            session,
            resource_id=resource_id,
            for_update=True,
        )

        if resource is None or not resource.is_active:
            raise ResourceValidationError(
                "The selected response resource does not exist or is inactive."
            )

        if fetch_active_resource_assignment(
            session,
            resource_id=resource_id,
            for_update=True,
        ) is not None:
            raise ResourceStateError(
                "This resource is already assigned to an active incident."
            )

        if resource.status != "Available":
            raise ResourceStateError(
                f"Resource {resource.resource_code} is {resource.status}, "
                "not Available."
            )

        now = datetime.now(MANILA_TIMEZONE)

        assignment = IncidentResourceAssignment(
            incident_id=incident_id,
            resource_id=resource_id,
            assigned_by_user_id=actor.id,
            assigned_by=_snapshot(actor),
            assigned_at=now,
            notes=(
                notes.strip()
                if notes and notes.strip()
                else None
            ),
        )

        resource.status = "Assigned"

        if resource.resource_type == "Response Team":
            incident.assigned_team = (
                f"{resource.resource_code} — {resource.name}"
            )
        elif resource.resource_type == "Vehicle":
            incident.assigned_vehicle = (
                f"{resource.resource_code} — {resource.name}"
            )

        session.add(assignment)
        session.flush()

        _add_incident_history(
            session,
            incident_id=incident_id,
            change_type="Resource Assigned",
            resource_name=(
                f"{resource.resource_code} — {resource.name}"
            ),
            new_value="Assigned",
            notes=(
                assignment.notes
                or "Response resource assigned."
            ),
            actor=actor,
            effective_at=now,
        )

        session.flush()
        return int(assignment.id)


def release_resource_assignment(
    *,
    assignment_id: int,
    notes: str,
    actor_user_id: int,
) -> None:
    cleaned_notes = notes.strip()

    if not cleaned_notes:
        raise ResourceValidationError(
            "Release notes are required."
        )

    with session_scope() as session:
        actor = _require_manager(
            session,
            user_id=actor_user_id,
        )

        assignment = fetch_assignment_by_id(
            session,
            assignment_id=assignment_id,
            for_update=True,
        )

        if (
            assignment is None
            or assignment.released_at is not None
        ):
            raise ResourceStateError(
                "The selected assignment is no longer active."
            )

        resource = fetch_resource_by_id(
            session,
            resource_id=int(assignment.resource_id),
            for_update=True,
        )

        if resource is None:
            raise ResourceDataIntegrityError(
                "The assigned response resource could not be found."
            )

        now = datetime.now(MANILA_TIMEZONE)
        assignment.released_at = now
        resource.status = "Available"

        incident = fetch_incident_by_id(
            session,
            incident_id=int(assignment.incident_id),
            for_update=True,
        )
        if incident is not None:
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

        _add_incident_history(
            session,
            incident_id=int(assignment.incident_id),
            change_type="Resource Released",
            resource_name=(
                f"{resource.resource_code} — {resource.name}"
            ),
            new_value="Available",
            notes=cleaned_notes,
            actor=actor,
            effective_at=now,
        )

        session.flush()
