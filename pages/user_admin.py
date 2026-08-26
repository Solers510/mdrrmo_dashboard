from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from config.access_control import (
    APP_ROLES,
    PERMISSION_MANAGE_USERS,
    ROLE_ADMINISTRATOR,
    ROLE_PERMISSIONS,
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
from utils.ui import (
    render_attention_required,
    render_dashboard_section_header,
    render_kpi_grid,
    render_operational_page_header,
    render_workflow_section,
)


current_user = require_permission(
    PERMISSION_MANAGE_USERS
)


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

PERMISSION_LABELS = {
    "view_dashboard": "Situation dashboard",
    "manage_events": "Event control",
    "submit_barangay_updates": "Barangay updates",
    "validate_barangay_reports": "Report validation",
    "manage_evacuation_centers": "Evacuation-center registry",
    "submit_evacuation_updates": "Evacuation updates",
    "manage_incidents": "Incident operations",
    "view_reports": "Situation reports and exports",
    "manage_users": "User administration",
}

ROLE_PURPOSES = {
    "Viewer": "Situation dashboard only",
    "Executive": "Dashboard and situation reports",
    "Encoder": "Barangay and evacuation data entry",
    "Validator": "Report validation and situation reports",
    "Operations Officer": (
        "Operational workspaces except user administration"
    ),
    "Administrator": "Full system access and user administration",
}


def format_datetime(value: object) -> str:
    if not isinstance(value, datetime):
        return "Not available"

    localized = (
        value.replace(tzinfo=MANILA_TIMEZONE)
        if value.tzinfo is None
        else value.astimezone(MANILA_TIMEZONE)
    )
    return localized.strftime("%d %B %Y, %I:%M %p")


def role_access_summary(role: str) -> str:
    permissions = ROLE_PERMISSIONS.get(role, frozenset())
    labels = [
        label
        for permission, label in PERMISSION_LABELS.items()
        if permission in permissions
    ]
    return ", ".join(labels) if labels else "No application access"


def account_label(
    user_id: int,
    user_by_id: dict[int, dict[str, object]],
) -> str:
    user = user_by_id[user_id]
    status = "Active" if user["is_active"] else "Inactive"
    current_marker = " — You" if user_id == current_user.id else ""
    return (
        f"{user['display_name']} — {user['email']} — "
        f"{status}{current_marker}"
    )


render_operational_page_header(
    title="User Access Administration",
    subtitle=(
        "Authorize OIDC identities, assign application roles, and maintain "
        "safe administrative access."
    ),
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

active_user_count = sum(
    1 for user in users if user["is_active"]
)
inactive_user_count = len(users) - active_user_count
active_administrator_count = sum(
    1
    for user in users
    if (
        user["role"] == ROLE_ADMINISTRATOR
        and user["is_active"]
    )
)

render_dashboard_section_header(
    title="Access Control Picture",
    subtitle=(
        "Current authorized-account status and Administrator continuity."
    ),
)

render_kpi_grid(
    [
        {
            "label": "Authorized Accounts",
            "value": len(users),
        },
        {
            "label": "Active Accounts",
            "value": active_user_count,
        },
        {
            "label": "Inactive Accounts",
            "value": inactive_user_count,
        },
        {
            "label": "Active Administrators",
            "value": active_administrator_count,
        },
    ]
)

if active_administrator_count == 1:
    render_attention_required(
        [
            {
                "label": "1 Active Administrator",
                "value": "No Backup Administrator",
                "tone": "warning",
            }
        ]
    )

directory_tab, authorize_tab, manage_tab, roles_tab = st.tabs(
    (
        f"Account Directory ({len(users)})",
        "Authorize Account",
        "Manage Account",
        "Role Guide",
    )
)

with directory_tab:
    render_dashboard_section_header(
        title="Authorized Account Directory",
        subtitle=(
            "Review account status, assigned role, OIDC email, and recent "
            "administrative updates."
        ),
    )

    if not users:
        st.info(
            "No application users exist."
        )
    else:
        directory_rows = [
            {
                "Status": (
                    "Active" if user["is_active"] else "Inactive"
                ),
                "Name": user["display_name"],
                "Email": user["email"],
                "Role": user["role"],
                "Account": (
                    "You"
                    if int(user["id"]) == current_user.id
                    else f"#{int(user['id'])}"
                ),
                "Updated": format_datetime(user["updated_at"]),
            }
            for user in users
        ]

        st.dataframe(
            pd.DataFrame(directory_rows),
            width="stretch",
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn(
                    "Status",
                    width=80,
                    pinned=True,
                ),
                "Name": st.column_config.TextColumn(
                    "Name",
                    width=170,
                ),
                "Email": st.column_config.TextColumn(
                    "OIDC Email",
                    width=230,
                ),
                "Role": st.column_config.TextColumn(
                    "Role",
                    width=135,
                ),
                "Account": st.column_config.TextColumn(
                    "Account",
                    width=75,
                ),
                "Updated": st.column_config.TextColumn(
                    "Updated",
                    width=165,
                ),
            },
        )

        st.caption(
            "Authentication remains with the configured OIDC provider. This "
            "directory controls authorization inside the MDRRMO system."
        )

with authorize_tab:
    render_dashboard_section_header(
        title="Authorize New Account",
        subtitle=(
            "Match an OIDC identity to one application role and activate "
            "its authorized system access."
        ),
    )

    with st.form(
        "create_application_user",
        clear_on_submit=False,
    ):
        render_workflow_section(
            step=1,
            title="Confirm Identity",
            subtitle=(
                "Enter the exact email address used with the configured "
                "identity provider and the person's operational name."
            ),
        )

        identity_columns = st.columns(2)
        email = identity_columns[0].text_input(
            "OIDC account email *",
            placeholder="name@example.com",
        )
        display_name = identity_columns[1].text_input(
            "Display name *",
            placeholder="Juan Dela Cruz",
        )

        render_workflow_section(
            step=2,
            title="Assign Application Role",
            subtitle=(
                "Choose the least-privilege role that matches the person's "
                "approved operational duties."
            ),
        )

        role = st.selectbox(
            "Application role *",
            options=APP_ROLES,
        )
        st.caption(
            f"Access granted: {role_access_summary(role)}."
        )

        render_workflow_section(
            step=3,
            title="Review & Authorize",
            subtitle=(
                "Verify the identity and role. New accounts become active "
                "immediately and the authorization is audited."
            ),
        )

        st.info(
            "Email matching is case-insensitive and the saved address is "
            "normalized. Existing authorized emails cannot be duplicated."
        )

        confirmation = st.checkbox(
            "I verified this person's identity and intended role."
        )
        submitted = st.form_submit_button(
            "Authorize Account",
            type="primary",
            width="stretch",
            disabled=not confirmation,
        )

    if submitted:
        try:
            user_id = create_app_user(
                email=email,
                display_name=display_name,
                role=role,
                actor_user_id=current_user.id,
            )
        except (
            UserAdminValidationError,
            UserAdminPermissionError,
            UserAdminIntegrityError,
            UserAdminServiceError,
        ) as error:
            st.error(str(error))
        else:
            st.session_state[
                "user_admin_success"
            ] = (
                f"Application user #{user_id} "
                "was authorized successfully."
            )
            st.rerun()

with manage_tab:
    render_dashboard_section_header(
        title="Manage Authorized Account",
        subtitle=(
            "Update an account's display name, application role, or active "
            "authorization status."
        ),
    )

    if not users:
        st.info(
            "No application account is available to manage."
        )
    else:
        user_by_id = {
            int(user["id"]): user
            for user in users
        }
        user_ids = list(user_by_id)
        selected_user_id = st.selectbox(
            "Authorized account",
            options=user_ids,
            format_func=lambda user_id: account_label(
                user_id,
                user_by_id,
            ),
        )
        selected_user = user_by_id[selected_user_id]
        is_current_account = (
            selected_user_id == current_user.id
        )
        is_final_active_administrator = (
            selected_user["role"] == ROLE_ADMINISTRATOR
            and selected_user["is_active"]
            and active_administrator_count <= 1
        )
        role_and_status_locked = (
            is_current_account
            or is_final_active_administrator
        )

        st.markdown(
            f"### {selected_user['display_name']}"
        )
        render_kpi_grid(
            [
                {
                    "label": "Status",
                    "value": (
                        "Active"
                        if selected_user["is_active"]
                        else "Inactive"
                    ),
                },
                {
                    "label": "Role",
                    "value": selected_user["role"],
                },
                {
                    "label": "Account",
                    "value": (
                        "Current User"
                        if is_current_account
                        else f"#{selected_user_id}"
                    ),
                },
                {
                    "label": "Last Updated",
                    "value": format_datetime(
                        selected_user["updated_at"]
                    ),
                },
            ]
        )

        if is_current_account:
            st.warning(
                "Your own Administrator role and active status are locked "
                "to prevent accidental loss of access. Your display name "
                "may still be updated."
            )
        elif is_final_active_administrator:
            st.warning(
                "This is the final active Administrator account. Its role "
                "and status are locked until another Administrator is active."
            )

        current_role_index = APP_ROLES.index(
            str(selected_user["role"])
        )

        with st.form(
            f"edit_application_user_{selected_user_id}"
        ):
            st.text_input(
                "OIDC email",
                value=str(selected_user["email"]),
                disabled=True,
            )
            edited_name = st.text_input(
                "Display name *",
                value=str(selected_user["display_name"]),
            )
            edit_columns = st.columns(2)
            edited_role = edit_columns[0].selectbox(
                "Application role *",
                options=APP_ROLES,
                index=current_role_index,
                disabled=role_and_status_locked,
            )
            edited_active = edit_columns[1].checkbox(
                "Account active",
                value=bool(selected_user["is_active"]),
                disabled=role_and_status_locked,
            )

            change_pending = (
                edited_name.strip()
                != str(selected_user["display_name"])
                or edited_role != selected_user["role"]
                or edited_active != bool(selected_user["is_active"])
            )
            sensitive_change = (
                selected_user["is_active"]
                and (
                    not edited_active
                    or (
                        selected_user["role"] == ROLE_ADMINISTRATOR
                        and edited_role != ROLE_ADMINISTRATOR
                    )
                )
            )
            sensitive_confirmation = True
            if sensitive_change:
                sensitive_confirmation = st.checkbox(
                    "I confirm this change removes active access or "
                    "Administrator authority."
                )

            if not change_pending:
                st.caption(
                    "Change the display name, role, or account status to save."
                )

            save_changes = st.form_submit_button(
                "Save Account Changes",
                type="primary",
                width="stretch",
                disabled=(
                    not change_pending
                    or not sensitive_confirmation
                ),
            )

        if save_changes:
            try:
                update_app_user(
                    user_id=selected_user_id,
                    display_name=edited_name,
                    role=edited_role,
                    is_active=edited_active,
                    actor_user_id=current_user.id,
                )
            except (
                UserAdminValidationError,
                UserAdminPermissionError,
                UserAdminIntegrityError,
                UserAdminServiceError,
            ) as error:
                st.error(str(error))
            else:
                st.session_state[
                    "user_admin_success"
                ] = "User account updated successfully."
                st.rerun()

with roles_tab:
    render_dashboard_section_header(
        title="Application Role Guide",
        subtitle=(
            "Compare the system capabilities granted by each approved role "
            "before authorizing or changing an account."
        ),
    )

    role_rows = [
        {
            "Role": role_name,
            "Operational Purpose": ROLE_PURPOSES[role_name],
            "Permission Count": len(
                ROLE_PERMISSIONS.get(role_name, frozenset())
            ),
        }
        for role_name in APP_ROLES
    ]

    st.dataframe(
        pd.DataFrame(role_rows),
        width="stretch",
        hide_index=True,
        column_config={
            "Role": st.column_config.TextColumn(
                "Role",
                width=155,
                pinned=True,
            ),
            "Operational Purpose": st.column_config.TextColumn(
                "Operational Purpose",
                width=430,
            ),
            "Permission Count": st.column_config.NumberColumn(
                "Permissions",
                width=90,
                format="%d",
            ),
        },
    )

    selected_guide_role = st.selectbox(
        "Inspect exact role permissions",
        options=APP_ROLES,
        index=APP_ROLES.index(ROLE_ADMINISTRATOR),
        key="role_guide_select",
    )
    selected_permissions = [
        {
            "Granted Capability": label,
        }
        for permission, label in PERMISSION_LABELS.items()
        if permission in ROLE_PERMISSIONS[selected_guide_role]
    ]

    st.markdown(
        f"### {selected_guide_role} Permissions"
    )
    st.dataframe(
        pd.DataFrame(selected_permissions),
        width="stretch",
        hide_index=True,
        column_config={
            "Granted Capability": st.column_config.TextColumn(
                "Granted Capability",
                width=620,
            ),
        },
    )

    st.info(
        "Role definitions are centrally enforced by the application. "
        "Administrators assign roles but cannot customize individual "
        "permissions from this page."
    )
