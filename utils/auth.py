from datetime import datetime, timezone
from typing import Any

import streamlit as st

from services.access_service import (
    AccessServiceError,
    CurrentAppUser,
    InvalidUserRoleError,
    UserInactiveError,
    UserNotAuthorizedError,
    resolve_app_user,
)


def login_screen() -> None:
    """
    Display the application login page.
    """
    st.title("MDRRMO Naic Operations Dashboard")

    st.write(
        "Sign in using an authorized municipal or "
        "development account."
    )

    if st.button(
        "Sign in",
        type="primary",
        use_container_width=True,
    ):
        st.login()

    st.stop()


def _identity_claims() -> dict[str, Any]:
    """
    Return the current OIDC identity claims.
    """
    if not getattr(
        st.user,
        "is_logged_in",
        False,
    ):
        login_screen()

    return st.user.to_dict()


def _enforce_identity_expiration(
    claims: dict[str, Any],
) -> None:
    """
    Log out when the identity token is already expired.
    """
    expires_at = claims.get("exp")

    if expires_at is None:
        return

    try:
        expiration_timestamp = int(expires_at)

    except (TypeError, ValueError):
        return

    current_timestamp = int(
        datetime.now(timezone.utc).timestamp()
    )

    if current_timestamp >= expiration_timestamp:
        st.warning(
            "Your authentication has expired. "
            "Sign in again."
        )

        st.logout()
        st.stop()


def get_current_app_user() -> CurrentAppUser:
    """
    Resolve the current OIDC identity into an application
    user and enforce authorization.
    """
    claims = _identity_claims()

    _enforce_identity_expiration(claims)

    email = str(
        claims.get("email", "")
    ).strip().lower()

    try:
        return resolve_app_user(
            email=email,
        )

    except UserNotAuthorizedError as error:
        st.error(str(error))

    except UserInactiveError as error:
        st.error(str(error))

    except InvalidUserRoleError as error:
        st.error(str(error))

    except AccessServiceError as error:
        st.error(str(error))

    if st.button(
        "Sign out",
        use_container_width=True,
    ):
        st.logout()

    st.stop()


def has_permission(
    user: CurrentAppUser,
    permission: str,
) -> bool:
    """
    Check whether a user has one permission.
    """
    return permission in user.permissions


def has_any_permission(
    user: CurrentAppUser,
    *permissions: str,
) -> bool:
    """
    Check whether a user has at least one permission.
    """
    return any(
        permission in user.permissions
        for permission in permissions
    )


def require_permission(
    permission: str,
) -> CurrentAppUser:
    """
    Stop a page when the current user lacks permission.
    """
    user = get_current_app_user()

    if not has_permission(
        user,
        permission,
    ):
        st.error(
            "You do not have permission to access "
            "this page."
        )
        st.stop()

    return user


def require_any_permission(
    *permissions: str,
) -> CurrentAppUser:
    """
    Stop a page unless the user has one allowed permission.
    """
    user = get_current_app_user()

    if not has_any_permission(
        user,
        *permissions,
    ):
        st.error(
            "You do not have permission to access "
            "this page."
        )
        st.stop()

    return user


def render_account_sidebar(
    user: CurrentAppUser,
) -> None:
    """
    Show the authenticated account and logout control.
    """
    with st.sidebar:
        st.divider()

        st.caption("Signed in as")

        st.write(
            f"**{user.display_name}**"
        )

        st.caption(
            f"{user.email} · {user.role}"
        )

        if st.button(
            "Sign out",
            use_container_width=True,
        ):
            st.logout()