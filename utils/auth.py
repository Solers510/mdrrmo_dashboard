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
from utils.app_logging import (
    get_app_logger,
)
from utils.ui import (
    render_identity_card,
    render_login_header,
)


logger = get_app_logger("auth")

CURRENT_APP_USER_SESSION_KEY = (
    "_mdrrmo_current_app_user"
)
CURRENT_APP_USER_EMAIL_SESSION_KEY = (
    "_mdrrmo_current_app_user_email"
)


def login_screen() -> None:
    """
    Display the application login page.
    """
    render_login_header()

    if st.button(
        "Sign in",
        type="primary",
        width="stretch",
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

        clear_current_app_user_session_cache()
        st.logout()
        st.stop()


def _read_cached_current_app_user(
    state,
    *,
    email: str,
) -> CurrentAppUser | None:
    cached_email = str(
        state.get(
            CURRENT_APP_USER_EMAIL_SESSION_KEY,
            "",
        )
    ).strip().lower()
    cached_user = state.get(
        CURRENT_APP_USER_SESSION_KEY
    )

    if (
        cached_email != email
        or not isinstance(
            cached_user,
            CurrentAppUser,
        )
    ):
        return None

    return cached_user


def _write_current_app_user_state(
    state,
    user: CurrentAppUser,
) -> None:
    state[
        CURRENT_APP_USER_SESSION_KEY
    ] = user
    state[
        CURRENT_APP_USER_EMAIL_SESSION_KEY
    ] = user.email


def _clear_current_app_user_state(
    state,
) -> None:
    state.pop(
        CURRENT_APP_USER_SESSION_KEY,
        None,
    )
    state.pop(
        CURRENT_APP_USER_EMAIL_SESSION_KEY,
        None,
    )


def clear_current_app_user_session_cache() -> None:
    """
    Remove the per-session authorization object.

    The app entry point refreshes authorization from PostgreSQL on every
    Streamlit rerun. The selected page can then reuse that same freshly
    resolved object without a second database lookup in the same rerun.
    """
    _clear_current_app_user_state(
        st.session_state
    )


def get_current_app_user(
    *,
    refresh_authorization: bool = False,
) -> CurrentAppUser:
    """
    Resolve the current OIDC identity into an application user.

    `app.py` calls this with refresh_authorization=True before navigation,
    preserving a fresh database authorization check on every Streamlit
    rerun. Page-level permission guards reuse that same per-session object
    later in the same rerun instead of querying PostgreSQL again.
    """
    claims = _identity_claims()

    _enforce_identity_expiration(claims)

    email = str(
        claims.get("email", "")
    ).strip().lower()

    if not refresh_authorization:
        cached_user = (
            _read_cached_current_app_user(
                st.session_state,
                email=email,
            )
        )

        if cached_user is not None:
            return cached_user

    try:
        user = resolve_app_user(
            email=email,
        )
        _write_current_app_user_state(
            st.session_state,
            user,
        )
        return user

    except UserNotAuthorizedError as error:
        clear_current_app_user_session_cache()
        st.error(str(error))

    except UserInactiveError as error:
        clear_current_app_user_session_cache()
        st.error(str(error))

    except InvalidUserRoleError as error:
        clear_current_app_user_session_cache()
        st.error(str(error))

    except AccessServiceError:
        clear_current_app_user_session_cache()
        logger.exception(
            "Application authorization lookup failed."
        )
        st.error(
            "The application could not verify your authorization. "
            "The database may be temporarily unavailable. "
            "Try again shortly."
        )

    if st.button(
        "Sign out",
        width="stretch",
    ):
        clear_current_app_user_session_cache()
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

        render_identity_card(
            display_name=user.display_name,
            email=user.email,
            role=user.role,
        )

        if st.button(
            "Sign out",
            width="stretch",
        ):
            clear_current_app_user_session_cache()
            st.logout()