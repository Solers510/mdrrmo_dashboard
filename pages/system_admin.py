import json

import pandas as pd
import streamlit as st

from config.access_control import PERMISSION_MANAGE_USERS
from services.audit_service import AuditServiceError, list_audit_entries
from services.backup_service import (
    BackupServiceError,
    create_database_backup,
    list_backups,
)
from services.system_health_service import (
    overall_health_status,
    run_system_health_checks,
)
from utils.auth import require_permission
from utils.error_handling import log_exception

current_user = require_permission(PERMISSION_MANAGE_USERS)

st.title("System Health, Audit and Recovery")
st.caption(
    "Administrator-only reliability tools for the MDRRMO prototype."
)

health_tab, audit_tab, backup_tab = st.tabs(
    ("System Health", "Audit Log", "Backup & Restore")
)

with health_tab:
    st.subheader("System Health Checks")

    try:
        health_rows = run_system_health_checks()
    except Exception as error:
        reference = log_exception("System Health page", error)
        st.error("System health checks could not be completed.")
        st.caption(f"Error reference: {reference}")
        health_rows = []

    if health_rows:
        status = overall_health_status(health_rows)
        if status == "PASS":
            st.success("All current prototype health checks passed.")
        elif status == "WARN":
            st.warning("Health checks completed with warnings.")
        else:
            st.error("One or more health checks failed.")

        summary = st.columns(3)
        summary[0].metric(
            "Passed", sum(row["status"] == "PASS" for row in health_rows)
        )
        summary[1].metric(
            "Warnings", sum(row["status"] == "WARN" for row in health_rows)
        )
        summary[2].metric(
            "Failed", sum(row["status"] == "FAIL" for row in health_rows)
        )

        st.dataframe(
            pd.DataFrame(health_rows),
            use_container_width=True,
            hide_index=True,
        )

with audit_tab:
    st.subheader("Append-Only System Audit Log")
    st.info(
        "PostgreSQL triggers capture changes to critical operational and "
        "administrative tables. The application has no edit/delete action "
        "for audit records."
    )

    try:
        audit_rows = list_audit_entries(limit=500)
    except AuditServiceError as error:
        st.error(str(error))
        audit_rows = []
    except Exception as error:
        reference = log_exception("Audit Log page", error)
        st.error("The audit log could not be loaded.")
        st.caption(f"Error reference: {reference}")
        audit_rows = []

    if not audit_rows:
        st.info(
            "No audited changes have been recorded since the audit "
            "infrastructure was installed."
        )
    else:
        table_options = sorted({str(row["table_name"]) for row in audit_rows})
        operation_options = sorted({str(row["operation"]) for row in audit_rows})

        filters = st.columns(2)
        selected_tables = filters[0].multiselect(
            "Tables", options=table_options
        )
        selected_operations = filters[1].multiselect(
            "Operations", options=operation_options
        )

        filtered_rows = [
            row
            for row in audit_rows
            if (not selected_tables or row["table_name"] in selected_tables)
            and (
                not selected_operations
                or row["operation"] in selected_operations
            )
        ]

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Audit ID": row["id"],
                        "When": row["occurred_at"],
                        "Table": row["table_name"],
                        "Operation": row["operation"],
                        "Record ID": row["record_id"],
                        "Actor": row["actor_snapshot"],
                    }
                    for row in filtered_rows
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        if filtered_rows:
            row_by_id = {int(row["id"]): row for row in filtered_rows}
            selected_audit_id = st.selectbox(
                "Inspect audit entry",
                options=list(row_by_id),
                format_func=lambda audit_id: (
                    f"#{audit_id} - {row_by_id[audit_id]['operation']} "
                    f"{row_by_id[audit_id]['table_name']}"
                ),
            )
            selected = row_by_id[selected_audit_id]

            before_column, after_column = st.columns(2)
            with before_column:
                st.markdown("**Previous row state**")
                st.code(
                    json.dumps(selected["old_data"], indent=2, default=str)
                    if selected["old_data"] is not None
                    else "No previous row state.",
                    language="json",
                )
            with after_column:
                st.markdown("**New row state**")
                st.code(
                    json.dumps(selected["new_data"], indent=2, default=str)
                    if selected["new_data"] is not None
                    else "No new row state.",
                    language="json",
                )

with backup_tab:
    st.subheader("Verified PostgreSQL Backups")
    st.warning(
        "Prototype backups are stored on the machine running the app. "
        "Off-machine/off-site retention remains a deployment requirement."
    )

    if st.button(
        "Create Verified Backup Now",
        type="primary",
        use_container_width=True,
    ):
        try:
            result = create_database_backup()
        except BackupServiceError as error:
            st.error(str(error))
        except Exception as error:
            reference = log_exception("Administrator backup action", error)
            st.error("The backup could not be created.")
            st.caption(f"Error reference: {reference}")
        else:
            st.success("Verified PostgreSQL backup created successfully.")
            st.write("**Backup file:**", result["backup_path"])
            st.write("**SHA-256:**", result["sha256"])

    backup_rows = list_backups()
    if backup_rows:
        st.dataframe(
            pd.DataFrame(backup_rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No local backup archives are currently listed.")

    st.markdown("### Restore Drill")
    st.write(
        "Run the restore test from the PyCharm terminal. It creates a "
        "temporary database only when the configured PostgreSQL role has "
        "CREATEDB permission, verifies the restored revision/table counts, "
        "and removes the temporary database."
    )
    st.code("python scripts/restore_test.py --latest", language="powershell")
