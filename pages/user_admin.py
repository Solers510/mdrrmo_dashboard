import pandas as pd
import streamlit as st

from config.access_control import (
    APP_ROLES,
    PERMISSION_MANAGE_USERS,
)
from services.user_admin_service import (
    UserAdminIntegrityError,
    UserAdminPermissionError,
    UserAdminServiceError,
    UserAdminValidationError,
    create_app_user,
    list_app_users,
    update_app_user,
)
from utils.auth import require_permission


current_user = require_permission(
    PERMISSION_MANAGE_USERS
)


st.title("User Administration")

st.caption(
    "Authorize users and control their application roles."
)


success_message = st.session_state.pop(
    "user_admin_success",
    None,
)

if success_message:
    st.success(success_message)


try:
    users = list_app_users()

except UserAdminServiceError as error:
    st.error(str(error))
    st.stop()


active_users = sum(
    1
    for user in users
    if user["is_active"]
)

administrators = sum(
    1
    for user in users
    if (
        user["role"] == "Administrator"
        and user["is_active"]
    )
)


summary_columns = st.columns(3)

with summary_columns[0]:
    st.metric(
        "Authorized Accounts",
        len(users),
    )

with summary_columns[1]:
    st.metric(
        "Active Accounts",
        active_users,
    )

with summary_columns[2]:
    st.metric(
        "Active Administrators",
        administrators,
    )


st.divider()


add_tab, manage_tab = st.tabs(
    (
        "Add User",
        "Manage Users",
    )
)


# ---------------------------------------------------------
# ADD USER
# ---------------------------------------------------------

with add_tab:
    st.subheader("Authorize New User")

    st.info(
        "The email must exactly match the Google "
        "account the person will use to sign in."
    )

    with st.form(
        "create_application_user"
    ):
        email = st.text_input(
            "Google account email *",
            placeholder="name@example.com",
        )

        display_name = st.text_input(
            "Display name *",
            placeholder="Juan Dela Cruz",
        )

        role = st.selectbox(
            "Application role *",
            options=APP_ROLES,
        )

        confirmation = st.checkbox(
            "I verified this person's identity "
            "and intended role."
        )

        submitted = st.form_submit_button(
            "Authorize User",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not confirmation:
            st.error(
                "Confirm the account information "
                "before creating the user."
            )

        else:
            try:
                user_id = create_app_user(
                    email=email,
                    display_name=display_name,
                    role=role,
                    actor_user_id=(
                        current_user.id
                    ),
                )

            except (
                UserAdminValidationError,
                UserAdminPermissionError,
                UserAdminIntegrityError,
            ) as error:
                st.error(str(error))

            except UserAdminServiceError as error:
                st.error(str(error))

            else:
                st.session_state[
                    "user_admin_success"
                ] = (
                    f"Application user #{user_id} "
                    "was authorized successfully."
                )

                st.rerun()


# ---------------------------------------------------------
# MANAGE USERS
# ---------------------------------------------------------

with manage_tab:
    st.subheader("Existing Users")

    if not users:
        st.info(
            "No application users exist."
        )

    else:
        table = pd.DataFrame(
            [
                {
                    "ID": user["id"],
                    "Name": user["display_name"],
                    "Email": user["email"],
                    "Role": user["role"],
                    "Active": user["is_active"],
                    "Created": user["created_at"],
                }
                for user in users
            ]
        )

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
        )


        user_by_id = {
            int(user["id"]): user
            for user in users
        }

        user_ids = list(
            user_by_id.keys()
        )


        def user_label(
            user_id: int,
        ) -> str:
            user = user_by_id[user_id]

            status = (
                "Active"
                if user["is_active"]
                else "Inactive"
            )

            return (
                f"{user['display_name']} "
                f"— {user['email']} "
                f"— {status}"
            )


        selected_user_id = st.selectbox(
            "Select user",
            options=user_ids,
            format_func=user_label,
        )

        selected_user = user_by_id[
            selected_user_id
        ]

        current_role_index = (
            APP_ROLES.index(
                selected_user["role"]
            )
        )

        with st.form(
            "edit_application_user"
        ):
            st.text_input(
                "Email",
                value=selected_user["email"],
                disabled=True,
            )

            edited_name = st.text_input(
                "Display name *",
                value=(
                    selected_user[
                        "display_name"
                    ]
                ),
            )

            edited_role = st.selectbox(
                "Role *",
                options=APP_ROLES,
                index=current_role_index,
            )

            edited_active = st.checkbox(
                "Account active",
                value=bool(
                    selected_user[
                        "is_active"
                    ]
                ),
            )

            save_changes = (
                st.form_submit_button(
                    "Save User Changes",
                    type="primary",
                    use_container_width=True,
                )
            )

        if save_changes:
            try:
                update_app_user(
                    user_id=(
                        selected_user_id
                    ),
                    display_name=edited_name,
                    role=edited_role,
                    is_active=edited_active,
                    actor_user_id=(
                        current_user.id
                    ),
                )

            except (
                UserAdminValidationError,
                UserAdminPermissionError,
                UserAdminIntegrityError,
            ) as error:
                st.error(str(error))

            except UserAdminServiceError as error:
                st.error(str(error))

            else:
                st.session_state[
                    "user_admin_success"
                ] = (
                    "User account updated "
                    "successfully."
                )

                st.rerun()