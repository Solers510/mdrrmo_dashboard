from datetime import datetime
import json
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from config.access_control import PERMISSION_MANAGE_USERS
from config.runtime import is_cloud_deployment
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
from utils.ui import (
    render_attention_required,
    render_dashboard_section_header,
    render_kpi_grid,
    render_operational_page_header,
    render_workflow_section,
)


current_user = require_permission(PERMISSION_MANAGE_USERS)
IS_CLOUD_DEPLOYMENT = is_cloud_deployment()


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")
HEALTH_STATUS_ORDER = {
    "FAIL": 0,
    "WARN": 1,
    "PASS": 2,
}
AUDIT_OPERATION_LABELS = {
    "INSERT": "Created",
    "UPDATE": "Updated",
    "DELETE": "Deleted",
}
DATA_AREA_LABELS = {
    "app_users": "Authorized Accounts",
    "barangay_updates": "Barangay Updates",
    "disaster_events": "Disaster Events",
    "evacuation_center_updates": "Evacuation Center Updates",
    "evacuation_centers": "Evacuation Centers",
    "incident_history": "Incident History",
    "incidents": "Incidents",
    "report_snapshots": "Report Snapshots",
    "response_resource_assignments": "Resource Assignments",
    "response_resources": "Response Resources",
}


def format_datetime(value: object) -> str:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value

    if not isinstance(value, datetime):
        return "Not available"

    localized = (
        value.replace(tzinfo=MANILA_TIMEZONE)
        if value.tzinfo is None
        else value.astimezone(MANILA_TIMEZONE)
    )
    return localized.strftime("%d %B %Y, %I:%M %p")


def format_size(value: object) -> str:
    try:
        size = max(0, int(value))
    except (TypeError, ValueError):
        return "Not available"

    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def compact_hash(value: object) -> str:
    digest = str(value or "").strip()
    return f"{digest[:12]}…" if len(digest) > 12 else digest or "Not recorded"


def format_short_datetime(value: object) -> tuple[str, str]:
    formatted = format_datetime(value)
    if formatted == "Not available" or ", " not in formatted:
        return formatted, ""

    date_text, time_text = formatted.rsplit(", ", maxsplit=1)
    return date_text, time_text


def archive_reference(value: object) -> str:
    filename = str(value or "").strip()
    return (
        filename.removeprefix("mdrrmo_dashboard_")
        .removesuffix(".backup")
    ) or "Not recorded"


def audit_operation_label(value: object) -> str:
    operation = str(value or "").upper()
    return AUDIT_OPERATION_LABELS.get(operation, operation.title() or "Unknown")


def audit_data_area_label(value: object) -> str:
    data_area = str(value or "").strip()
    return DATA_AREA_LABELS.get(
        data_area,
        data_area.replace("_", " ").title() or "Unknown",
    )


render_operational_page_header(
    title="System Reliability & Audit",
    subtitle=(
        "Monitor application readiness, inspect the immutable audit trail, "
        "and maintain verified PostgreSQL recovery evidence."
    ),
)

backup_success = st.session_state.pop(
    "system_admin_backup_success",
    None,
)
if backup_success:
    st.success(backup_success)

try:
    health_rows = run_system_health_checks()
except Exception as error:
    reference = log_exception("System Health page", error)
    st.error("System health checks could not be completed.")
    st.caption(f"Error reference: {reference}")
    health_rows = []

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

if IS_CLOUD_DEPLOYMENT:
    backup_rows = []
else:
    try:
        backup_rows = list_backups()
    except Exception as error:
        reference = log_exception("Backup archive page", error)
        st.error("The local backup archive could not be listed.")
        st.caption(f"Error reference: {reference}")
        backup_rows = []

passed_count = sum(row["status"] == "PASS" for row in health_rows)
warning_count = sum(row["status"] == "WARN" for row in health_rows)
failed_count = sum(row["status"] == "FAIL" for row in health_rows)
system_status = overall_health_status(health_rows) if health_rows else "UNKNOWN"
verified_backup_count = sum(
    row.get("archive_verified") is True for row in backup_rows
)
latest_backup = backup_rows[0] if backup_rows else None
latest_backup_date, latest_backup_time = format_short_datetime(
    latest_backup.get("created_at") if latest_backup else None
)

render_dashboard_section_header(
    title="Reliability Command Picture",
    subtitle=(
        "Current technical readiness, audit visibility, and recoverability "
        "evidence for this application instance."
    ),
)

recovery_metrics = (
    [
        {
            "label": "Independent Backup",
            "value": "Not Linked",
            "meta": "Manual evidence required",
        },
        {
            "label": "Recovery Provider",
            "value": "Aiven",
            "meta": "Verify in provider console",
        },
    ]
    if IS_CLOUD_DEPLOYMENT
    else [
        {
            "label": "Verified Backups",
            "value": verified_backup_count,
            "meta": f"{len(backup_rows)} local archives",
        },
        {
            "label": "Latest Backup",
            "value": latest_backup_date if latest_backup else "None",
            "meta": latest_backup_time,
        },
    ]
)

render_kpi_grid(
    [
        {
            "label": "System Status",
            "value": system_status,
            "meta": f"{len(health_rows)} checks completed",
        },
        {
            "label": "Failed Checks",
            "value": failed_count,
        },
        {
            "label": "Audit Entries Loaded",
            "value": len(audit_rows),
            "meta": "Latest 500 maximum",
        },
        *recovery_metrics,
    ]
)

attention_items = []
if failed_count:
    attention_items.append(
        {
            "label": "Failed Health Checks",
            "value": failed_count,
            "tone": "danger",
        }
    )
if warning_count:
    attention_items.append(
        {
            "label": "Health Warnings",
            "value": warning_count,
            "tone": "warning",
        }
    )
if IS_CLOUD_DEPLOYMENT:
    attention_items.extend(
        [
            {
                "label": "Independent Backup Evidence",
                "value": "Manual Verification",
                "tone": "warning",
            },
            {
                "label": "Aiven Recovery Status",
                "value": "Verify in Console",
                "tone": "warning",
            },
        ]
    )
elif not backup_rows:
    attention_items.append(
        {
            "label": "Recovery Evidence",
            "value": "No Local Backup",
            "tone": "warning",
        }
    )
elif verified_backup_count < len(backup_rows):
    attention_items.append(
        {
            "label": "Unverified Local Archives",
            "value": len(backup_rows) - verified_backup_count,
            "tone": "warning",
        }
    )

if not IS_CLOUD_DEPLOYMENT:
    attention_items.append(
        {
            "label": "Off-Machine Backup Retention",
            "value": "Manual Verification",
            "tone": "warning",
        }
    )

if attention_items:
    render_attention_required(attention_items)
else:
    st.success("No current reliability exception was detected by the automated checks.")

health_tab, audit_tab, backup_tab = st.tabs(
    (
        f"Health Checks ({len(health_rows)})",
        f"Audit Trail ({len(audit_rows)})",
        (
            "Cloud Recovery"
            if IS_CLOUD_DEPLOYMENT
            else f"Backup & Recovery ({len(backup_rows)})"
        ),
    )
)

with health_tab:
    render_dashboard_section_header(
        title="System Health Checks",
        subtitle=(
            "Review failed and warning conditions first, then confirm the "
            "supporting readiness detail for passing checks."
        ),
    )

    render_kpi_grid(
        [
            {"label": "Passed", "value": passed_count},
            {"label": "Warnings", "value": warning_count},
            {"label": "Failed", "value": failed_count},
        ],
        compact=True,
    )

    if not health_rows:
        st.info("No system health result is currently available.")
    else:
        ordered_health_rows = sorted(
            health_rows,
            key=lambda row: (
                HEALTH_STATUS_ORDER.get(str(row["status"]), 99),
                str(row["check"]),
            ),
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Status": row["status"],
                        "Check": row["check"],
                        "Detail": row["detail"],
                    }
                    for row in ordered_health_rows
                ]
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn(
                    "Status",
                    width=80,
                    pinned=True,
                ),
                "Check": st.column_config.TextColumn(
                    "Check",
                    width=220,
                ),
                "Detail": st.column_config.TextColumn(
                    "Readiness Detail",
                    width=560,
                ),
            },
        )

        if system_status == "PASS":
            st.info(
                "Automated checks passed. Production readiness still depends "
                "on the manual deployment and recovery gates in the runbook."
            )

with audit_tab:
    render_dashboard_section_header(
        title="Immutable System Audit Trail",
        subtitle=(
            "Filter recent changes by data area and operation, then inspect "
            "the exact recorded before-and-after state."
        ),
    )
    st.info(
        "PostgreSQL triggers append changes to critical operational and "
        "administrative tables. This application provides no edit or delete "
        "action for audit records."
    )

    if not audit_rows:
        st.info(
            "No audited changes have been recorded since the audit "
            "infrastructure was installed."
        )
    else:
        table_options = sorted(
            {str(row["table_name"]) for row in audit_rows}
        )
        operation_options = sorted(
            {str(row["operation"]) for row in audit_rows}
        )
        filters = st.columns(2)
        selected_tables = filters[0].multiselect(
            "Data areas",
            options=table_options,
            format_func=audit_data_area_label,
        )
        selected_operations = filters[1].multiselect(
            "Operations",
            options=operation_options,
            format_func=audit_operation_label,
        )

        filtered_rows = [
            row
            for row in audit_rows
            if (
                not selected_tables
                or str(row["table_name"]) in selected_tables
            )
            and (
                not selected_operations
                or str(row["operation"]) in selected_operations
            )
        ]

        st.caption(
            f"Showing {len(filtered_rows)} of {len(audit_rows)} loaded entries."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "When": format_datetime(row["occurred_at"]),
                        "Action": audit_operation_label(row["operation"]),
                        "Data Area": audit_data_area_label(row["table_name"]),
                        "Record": row["record_id"] or "—",
                        "Actor": row["actor_snapshot"] or "System",
                        "Audit ID": row["id"],
                    }
                    for row in filtered_rows
                ]
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "When": st.column_config.TextColumn(
                    "When",
                    width=175,
                    pinned=True,
                ),
                "Action": st.column_config.TextColumn(
                    "Action",
                    width=90,
                ),
                "Data Area": st.column_config.TextColumn(
                    "Data Area",
                    width=175,
                ),
                "Record": st.column_config.TextColumn(
                    "Record",
                    width=90,
                ),
                "Actor": st.column_config.TextColumn(
                    "Actor",
                    width=260,
                ),
                "Audit ID": st.column_config.NumberColumn(
                    "Audit ID",
                    width=80,
                    format="%d",
                ),
            },
        )

        if filtered_rows:
            row_by_id = {
                int(row["id"]): row for row in filtered_rows
            }
            selected_audit_id = st.selectbox(
                "Inspect exact audit entry",
                options=list(row_by_id),
                format_func=lambda audit_id: (
                    f"#{audit_id} — "
                    f"{audit_operation_label(row_by_id[audit_id]['operation'])} "
                    f"{audit_data_area_label(row_by_id[audit_id]['table_name'])} "
                    f"record {row_by_id[audit_id]['record_id'] or '—'}"
                ),
            )
            selected = row_by_id[selected_audit_id]

            inspection_columns = st.columns(3)
            inspection_columns[0].markdown(
                f"**Occurred:** {format_datetime(selected['occurred_at'])}"
            )
            inspection_columns[1].markdown(
                f"**Actor:** {selected['actor_snapshot'] or 'System'}"
            )
            inspection_columns[2].markdown(
                f"**Audit ID:** #{selected_audit_id}"
            )

            before_column, after_column = st.columns(2)
            with before_column:
                st.markdown("### Previous Row State")
                st.code(
                    json.dumps(
                        selected["old_data"],
                        indent=2,
                        default=str,
                        ensure_ascii=False,
                    )
                    if selected["old_data"] is not None
                    else "No previous row state.",
                    language="json",
                )
            with after_column:
                st.markdown("### New Row State")
                st.code(
                    json.dumps(
                        selected["new_data"],
                        indent=2,
                        default=str,
                        ensure_ascii=False,
                    )
                    if selected["new_data"] is not None
                    else "No new row state.",
                    language="json",
                )

with backup_tab:
    if IS_CLOUD_DEPLOYMENT:
        render_dashboard_section_header(
            title="Cloud Backup & Recovery",
            subtitle=(
                "Review the two required recovery layers for the cloud pilot: "
                "provider-managed recovery and an independent encrypted archive."
            ),
        )
        st.warning(
            "Streamlit Community Cloud storage is temporary. Local archive "
            "creation is disabled in this deployment and no backup file is "
            "retained by the application container."
        )

        provider_tab, independent_tab, cloud_restore_tab = st.tabs(
            (
                "Aiven Recovery",
                "Independent Archive",
                "Restore Drill Guidance",
            )
        )

        with provider_tab:
            render_workflow_section(
                step=1,
                title="Verify Provider Recovery",
                subtitle=(
                    "An authorized service owner must confirm the current "
                    "backup and recovery state in the Aiven Console."
                ),
            )
            st.info(
                "This application cannot independently verify or download "
                "Aiven-managed recovery backups. Record the console review in "
                "the approved backup register."
            )
            render_workflow_section(
                step=2,
                title="Preserve Provider Evidence",
                subtitle=(
                    "Record the review date, responsible custodian, service "
                    "name, and recovery status without copying credentials."
                ),
            )

        with independent_tab:
            render_workflow_section(
                step=1,
                title="Use a Trusted Backup Workstation",
                subtitle=(
                    "Run PostgreSQL client tools outside Streamlit using the "
                    "protected Aiven connection details."
                ),
            )
            st.code(
                "python scripts/backup_database.py --directory "
                '"<APPROVED_ENCRYPTED_BACKUP_FOLDER>"',
                language="powershell",
            )
            render_workflow_section(
                step=2,
                title="Retain the Complete Backup Set",
                subtitle=(
                    "Keep the .backup archive, metadata JSON, and SHA-256 "
                    "checksum together in approved off-platform storage."
                ),
            )
            st.warning(
                "Do not place database archives in GitHub, a public link, "
                "ordinary email, or Streamlit application storage."
            )

        with cloud_restore_tab:
            render_workflow_section(
                step=1,
                title="Use an Isolated PostgreSQL Target",
                subtitle=(
                    "Restore testing must use a disposable local or staging "
                    "server, never the live Aiven pilot database."
                ),
            )
            render_workflow_section(
                step=2,
                title="Verify Recovery Evidence",
                subtitle=(
                    "Compare the Alembic revision, audit triggers, table counts, "
                    "and integrity checksum before recording a successful drill."
                ),
            )
            st.warning(
                "Cloud restore operations remain intentionally unavailable as "
                "an in-app button. They require a controlled maintenance "
                "workstation and separately authorized credentials."
            )

        st.stop()

    render_dashboard_section_header(
        title="Verified Backup & Recovery",
        subtitle=(
            "Create and review verified local PostgreSQL archives, then use "
            "the controlled terminal procedure for restore testing."
        ),
    )
    st.warning(
        "These archives are stored on the application machine. Approved "
        "off-machine or off-site retention remains a production requirement."
    )

    render_kpi_grid(
        [
            {"label": "Local Archives", "value": len(backup_rows)},
            {"label": "Verified", "value": verified_backup_count},
            {
                "label": "Latest Backup",
                "value": latest_backup_date if latest_backup else "None",
                "meta": (
                    f"{latest_backup_time} · "
                    f"{format_size(latest_backup.get('size_bytes'))}"
                    if latest_backup
                    else "No local archive"
                ),
            },
        ],
        compact=True,
    )

    create_backup_tab, archive_tab, restore_tab = st.tabs(
        (
            "Create Verified Backup",
            f"Backup Archive ({len(backup_rows)})",
            "Restore Drill Guidance",
        )
    )

    with create_backup_tab:
        render_workflow_section(
            step=1,
            title="Confirm Backup Context",
            subtitle=(
                "The archive captures the configured PostgreSQL database, "
                "schema revision, and current table-count evidence."
            ),
        )
        st.info(
            "Creating a backup does not change operational records. It writes "
            "a new timestamped archive, metadata file, and SHA-256 checksum."
        )

        render_workflow_section(
            step=2,
            title="Authorize Local Archive Creation",
            subtitle=(
                "Confirm that the application machine is an approved temporary "
                "backup location before running PostgreSQL backup tools."
            ),
        )
        with st.form("create_verified_database_backup"):
            backup_confirmation = st.checkbox(
                "I authorize creation of a verified local database archive."
            )
            create_backup = st.form_submit_button(
                "Create Verified Backup",
                type="primary",
                width="stretch",
                disabled=not backup_confirmation,
            )

        if create_backup:
            try:
                result = create_database_backup()
            except BackupServiceError as error:
                st.error(str(error))
            except Exception as error:
                reference = log_exception(
                    "Administrator backup action",
                    error,
                )
                st.error("The backup could not be created.")
                st.caption(f"Error reference: {reference}")
            else:
                st.session_state[
                    "system_admin_backup_success"
                ] = (
                    "Verified PostgreSQL backup created: "
                    f"{result['backup_path']}"
                )
                st.rerun()

    with archive_tab:
        render_dashboard_section_header(
            title="Local Backup Archive",
            subtitle=(
                "Scan verification state, creation time, size, revision, and "
                "short integrity reference for each local archive."
            ),
        )
        if not backup_rows:
            st.info("No local backup archive is currently listed.")
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Archive Reference": archive_reference(
                                row["filename"]
                            ),
                            "Verified": (
                                "Yes"
                                if row.get("archive_verified") is True
                                else "No"
                            ),
                            "Created": format_datetime(row.get("created_at")),
                            "Size": format_size(row.get("size_bytes")),
                            "Revision": row.get("alembic_revision") or "—",
                            "Integrity": compact_hash(row.get("sha256")),
                        }
                        for row in backup_rows
                    ]
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "Archive Reference": st.column_config.TextColumn(
                        "Archive Reference",
                        width=160,
                        pinned=True,
                    ),
                    "Verified": st.column_config.TextColumn(
                        "Verified",
                        width=80,
                    ),
                    "Created": st.column_config.TextColumn(
                        "Created",
                        width=175,
                    ),
                    "Size": st.column_config.TextColumn(
                        "Size",
                        width=85,
                    ),
                    "Revision": st.column_config.TextColumn(
                        "Revision",
                        width=125,
                    ),
                    "Integrity": st.column_config.TextColumn(
                        "Integrity",
                        width=125,
                    ),
                },
            )

            backup_by_filename = {
                str(row["filename"]): row for row in backup_rows
            }
            selected_backup_name = st.selectbox(
                "Inspect backup evidence",
                options=list(backup_by_filename),
            )
            selected_backup = backup_by_filename[selected_backup_name]

            evidence_columns = st.columns(3)
            evidence_columns[0].markdown(
                "**Verification:** "
                + (
                    "Archive readable"
                    if selected_backup.get("archive_verified") is True
                    else "Verification not recorded"
                )
            )
            evidence_columns[1].markdown(
                "**Schema revision:** "
                f"{selected_backup.get('alembic_revision') or 'Not recorded'}"
            )
            evidence_columns[2].markdown(
                "**Size:** "
                f"{format_size(selected_backup.get('size_bytes'))}"
            )
            st.caption("SHA-256 integrity hash")
            st.code(
                str(selected_backup.get("sha256") or "Not recorded"),
                language=None,
            )
            st.caption("Local archive path")
            st.code(str(selected_backup["path"]), language=None)

    with restore_tab:
        render_dashboard_section_header(
            title="Controlled Restore Drill",
            subtitle=(
                "Use the dedicated maintenance workflow to verify restoration "
                "without overwriting the configured operational database."
            ),
        )
        st.info(
            "The restore drill creates a disposable database only when the "
            "configured maintenance role is authorized, restores the archive "
            "as the application role, verifies revision and table counts, and "
            "then removes the disposable database."
        )
        render_workflow_section(
            step=1,
            title="Keep PostgreSQL Running",
            subtitle="The drill requires access to the configured database server.",
        )
        render_workflow_section(
            step=2,
            title="Run the Latest Verified Archive",
            subtitle=(
                "Execute the controlled recovery script from the project "
                "terminal; passwords are prompted rather than passed as arguments."
            ),
        )
        st.code(
            "python scripts/restore_test.py --latest",
            language="powershell",
        )
        render_workflow_section(
            step=3,
            title="Preserve Recovery Evidence",
            subtitle=(
                "Review the reported schema, trigger, revision, and row-count "
                "checks before recording the drill as complete."
            ),
        )
        st.warning(
            "Restore operations are intentionally unavailable as an in-app "
            "button. They require terminal control and the dedicated "
            "restore-maintenance role."
        )
