from dataclasses import dataclass

from config.access_control import (
    APP_ROLES,
    permissions_for_role,
)
from database.connection import SessionLocal
from database.repositories import (
    fetch_app_user_by_email,
)


class AccessServiceError(Exception):
    """Base exception for user-access operations."""


class UserNotAuthorizedError(AccessServiceError):
    """Raised when the identity has no application account."""


class UserInactiveError(AccessServiceError):
    """Raised when an application account is inactive."""


class InvalidUserRoleError(AccessServiceError):
    """Raised when a stored role is invalid."""


@dataclass(frozen=True)
class CurrentAppUser:
    """
    Authorized application-user information.
    """

    id: int
    email: str
    display_name: str
    role: str
    permissions: frozenset[str]


def resolve_app_user(
    *,
    email: str,
) -> CurrentAppUser:
    """
    Resolve an authenticated Google identity into an
    authorized PostgreSQL application user.
    """
    normalized_email = email.strip().lower()

    if not normalized_email:
        raise UserNotAuthorizedError(
            "The identity provider did not supply "
            "an email address."
        )

    try:
        with SessionLocal() as session:
            user = fetch_app_user_by_email(
                session,
                email=normalized_email,
            )

            if user is None:
                raise UserNotAuthorizedError(
                    "Your Google identity is authenticated, "
                    "but it has not been authorized for "
                    "this system."
                )

            if not user.is_active:
                raise UserInactiveError(
                    "Your system account is inactive."
                )

            if user.role not in APP_ROLES:
                raise InvalidUserRoleError(
                    "Your application account has an "
                    "invalid role assignment."
                )

            return CurrentAppUser(
                id=int(user.id),
                email=str(user.email),
                display_name=str(user.display_name),
                role=str(user.role),
                permissions=permissions_for_role(
                    str(user.role)
                ),
            )

    except AccessServiceError:
        raise

    except Exception as error:
        raise AccessServiceError(
            "The application could not verify "
            "your authorization."
        ) from error