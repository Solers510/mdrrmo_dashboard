from config.access_control import (
    APP_ROLES,
    ROLE_ADMINISTRATOR,
)
from database.connection import (
    SessionLocal,
    session_scope,
)
from database.models import AppUser
from database.repositories import (
    fetch_all_app_users,
    fetch_app_user_by_email,
    fetch_app_user_by_id,
)


class UserAdminServiceError(Exception):
    """Base user-administration exception."""


class UserAdminValidationError(UserAdminServiceError):
    """Raised when user information is invalid."""


class UserAdminPermissionError(UserAdminServiceError):
    """Raised when an actor cannot manage users."""


class UserAdminIntegrityError(UserAdminServiceError):
    """Raised when a change would damage account integrity."""


def _normalize_email(
    email: str,
) -> str:
    normalized = email.strip().lower()

    if not normalized:
        raise UserAdminValidationError(
            "Email address is required."
        )

    if "@" not in normalized:
        raise UserAdminValidationError(
            "Enter a valid email address."
        )

    if len(normalized) > 320:
        raise UserAdminValidationError(
            "Email address is too long."
        )

    return normalized


def _validate_display_name(
    display_name: str,
) -> str:
    cleaned = display_name.strip()

    if not cleaned:
        raise UserAdminValidationError(
            "Display name is required."
        )

    if len(cleaned) > 150:
        raise UserAdminValidationError(
            "Display name cannot exceed 150 characters."
        )

    return cleaned


def _validate_role(
    role: str,
) -> None:
    if role not in APP_ROLES:
        raise UserAdminValidationError(
            "The selected role is invalid."
        )


def _require_administrator(
    session,
    *,
    actor_user_id: int,
) -> AppUser:
    actor = fetch_app_user_by_id(
        session,
        user_id=actor_user_id,
    )

    if actor is None:
        raise UserAdminPermissionError(
            "The administrator account could not be found."
        )

    if not actor.is_active:
        raise UserAdminPermissionError(
            "The administrator account is inactive."
        )

    if actor.role != ROLE_ADMINISTRATOR:
        raise UserAdminPermissionError(
            "Administrator permission is required."
        )

    return actor


def list_app_users() -> list[dict[str, object]]:
    """
    Return all authorized application accounts.
    """
    try:
        with SessionLocal() as session:
            users = fetch_all_app_users(session)

            return [
                {
                    "id": int(user.id),
                    "email": str(user.email),
                    "display_name": str(
                        user.display_name
                    ),
                    "role": str(user.role),
                    "is_active": bool(
                        user.is_active
                    ),
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                }
                for user in users
            ]

    except UserAdminServiceError:
        raise

    except Exception as error:
        raise UserAdminServiceError(
            "Application users could not be loaded."
        ) from error


def create_app_user(
    *,
    email: str,
    display_name: str,
    role: str,
    actor_user_id: int,
) -> int:
    """
    Authorize a new OIDC identity for the application.
    """
    normalized_email = _normalize_email(email)

    cleaned_name = _validate_display_name(
        display_name
    )

    _validate_role(role)

    with session_scope() as session:
        _require_administrator(
            session,
            actor_user_id=actor_user_id,
        )

        existing = fetch_app_user_by_email(
            session,
            email=normalized_email,
        )

        if existing is not None:
            raise UserAdminValidationError(
                "An application account already exists "
                "for this email address."
            )

        user = AppUser(
            email=normalized_email,
            display_name=cleaned_name,
            role=role,
            is_active=True,
        )

        session.add(user)
        session.flush()

        return int(user.id)


def update_app_user(
    *,
    user_id: int,
    display_name: str,
    role: str,
    is_active: bool,
    actor_user_id: int,
) -> None:
    """
    Update an application user's name, role or status.
    """
    if user_id <= 0:
        raise UserAdminValidationError(
            "A valid user account is required."
        )

    cleaned_name = _validate_display_name(
        display_name
    )

    _validate_role(role)

    with session_scope() as session:
        actor = _require_administrator(
            session,
            actor_user_id=actor_user_id,
        )

        target = fetch_app_user_by_id(
            session,
            user_id=user_id,
        )

        if target is None:
            raise UserAdminValidationError(
                "The selected account does not exist."
            )

        # Prevent an administrator from locking
        # themselves out accidentally.
        if target.id == actor.id:
            if not is_active:
                raise UserAdminIntegrityError(
                    "You cannot deactivate your own "
                    "administrator account."
                )

            if role != ROLE_ADMINISTRATOR:
                raise UserAdminIntegrityError(
                    "You cannot remove your own "
                    "Administrator role."
                )

        removing_active_admin = (
            target.role == ROLE_ADMINISTRATOR
            and target.is_active
            and (
                role != ROLE_ADMINISTRATOR
                or not is_active
            )
        )

        if removing_active_admin:
            users = fetch_all_app_users(
                session
            )

            active_admin_count = sum(
                1
                for user in users
                if (
                    user.role
                    == ROLE_ADMINISTRATOR
                    and user.is_active
                )
            )

            if active_admin_count <= 1:
                raise UserAdminIntegrityError(
                    "The final active Administrator "
                    "account cannot be removed or "
                    "deactivated."
                )

        target.display_name = cleaned_name
        target.role = role
        target.is_active = is_active

        session.flush()