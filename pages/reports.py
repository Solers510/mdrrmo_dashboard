from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from config.access_control import (
    PERMISSION_VIEW_REPORTS,
)
from services.export_service import (
    ExportServiceError,
    report_filename,
)
from services.report_service import (
    DuplicateReportGenerationError,
    NoActiveEventForReportError,
    REPORT_MODE_OFFICIAL,
    REPORT_MODE_PROVISIONAL,
    ReportAuthorizationError,
    ReportDataIntegrityError,
    ReportServiceError,
    ReportValidationError,
    create_report_snapshot,
    get_current_report_event,
    get_report_snapshot,
    list_report_snapshots,
)
from utils.auth import require_permission
from utils.report_export_cache import (
    ReportExportCacheError,
    get_report_export_bundle,
)
from utils.ui import (
    render_dashboard_section_header,
    render_kpi_grid,
    render_operational_event_strip,
    render_operational_page_header,
    render_workflow_section,
)


current_user = require_permission(
    PERMISSION_VIEW_REPORTS
)


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")


def display_event_name(event: dict[str, object]) -> str:
    name = str(event.get("event_name") or "Unnamed event")
    classification = event.get("classification")

    if classification is not None and str(classification).strip():
        return f"{classification} {name}"

    return name


def display_sitrep(value: object) -> str:
    if value in {None, ""}:
        return "Not set"

    return str(value)


def format_datetime(value: object) -> str:
    if not isinstance(value, datetime):
        return "Not available"

    localized = (
        value.replace(tzinfo=MANILA_TIMEZONE)
        if value.tzinfo is None
        else value.astimezone(MANILA_TIMEZONE)
    )
    return localized.strftime("%d %B %Y, %I:%M %p")


def compact_integrity_hash(value: object) -> str:
    digest = str(value or "").strip()
    if not digest:
        return "Not available"

    return f"{digest[:12]}…"


render_operational_page_header(
    title="Situation Reports & Exports",
    subtitle=(
        "Generate immutable situation-report snapshots, review their "
        "integrity, and export exactly what was recorded."
    ),
)

success_message = st.session_state.pop(
    "report_success",
    None,
)
if success_message:
    st.success(success_message)

try:
    active_event = get_current_report_event()
    snapshot_rows = list_report_snapshots(
        limit=100
    )
except ReportServiceError as error:
    st.error(str(error))
    st.stop()

if active_event is not None:
    render_operational_event_strip(
        event_name=display_event_name(active_event),
        hazard_type=str(active_event["hazard_type"]),
        alert_code=str(active_event["alert_code"]),
        eoc_status=str(active_event["eoc_status"]),
        sitrep=display_sitrep(
            active_event.get("current_sitrep_number")
        ),
        official_reference=(
            str(active_event["official_reference"])
            if active_event.get("official_reference")
            else None
        ),
    )
else:
    st.info(
        "No active disaster event exists. Historical snapshots remain "
        "available for integrity review and export."
    )

provisional_snapshot_count = sum(
    1
    for row in snapshot_rows
    if row["report_mode"] == REPORT_MODE_PROVISIONAL
)
official_snapshot_count = sum(
    1
    for row in snapshot_rows
    if row["report_mode"] == REPORT_MODE_OFFICIAL
)
latest_snapshot = snapshot_rows[0] if snapshot_rows else None

render_dashboard_section_header(
    title="Report Command Picture",
    subtitle=(
        "Current reporting context and immutable snapshot availability."
    ),
)

render_kpi_grid(
    [
        {
            "label": "Saved Snapshots",
            "value": len(snapshot_rows),
        },
        {
            "label": "Provisional",
            "value": provisional_snapshot_count,
        },
        {
            "label": "Official Validated",
            "value": official_snapshot_count,
        },
        {
            "label": "Latest Snapshot",
            "value": (
                f"#{int(latest_snapshot['id'])}"
                if latest_snapshot is not None
                else "None"
            ),
            "meta": (
                format_datetime(latest_snapshot["generated_at"])
                if latest_snapshot is not None
                else "No snapshot generated"
            ),
        },
    ]
)

create_tab, archive_tab, export_tab = st.tabs(
    (
        "Create Snapshot",
        f"Snapshot Archive ({len(snapshot_rows)})",
        "Review & Export",
    )
)

with create_tab:
    render_dashboard_section_header(
        title="Create Situation Report Snapshot",
        subtitle=(
            "Confirm the active event and data mode before creating an "
            "append-only operational record."
        ),
    )

    if active_event is None:
        st.info(
            "Snapshot generation is unavailable until a disaster event is "
            "active. Historical exports remain available in Review & Export."
        )
    else:
        render_workflow_section(
            step=1,
            title="Confirm Reporting Context",
            subtitle=(
                "Verify the active event and SitRep number shown above before "
                "capturing the report."
            ),
        )

        context_columns = st.columns(2)
        context_columns[0].caption(
            "Active event"
        )
        context_columns[0].write(
            display_event_name(active_event)
        )
        context_columns[1].caption(
            "Current SitRep"
        )
        context_columns[1].write(
            display_sitrep(
                active_event.get("current_sitrep_number")
            )
        )

        render_workflow_section(
            step=2,
            title="Choose Data Mode",
            subtitle=(
                "Select whether the snapshot captures current operational "
                "information or validated official totals."
            ),
        )

        report_mode = st.radio(
            "Report data mode",
            options=(
                REPORT_MODE_PROVISIONAL,
                REPORT_MODE_OFFICIAL,
            ),
            horizontal=True,
            help=(
                "Provisional captures the latest usable operational reports. "
                "Official Validated captures only validated source reports."
            ),
        )

        if report_mode == REPORT_MODE_PROVISIONAL:
            st.warning(
                "This snapshot may include submitted information that has "
                "not completed formal validation."
            )
        else:
            st.success(
                "This snapshot uses validated barangay, evacuation-center, "
                "and incident records for its official totals."
            )

        render_workflow_section(
            step=3,
            title="Authorize Immutable Snapshot",
            subtitle=(
                "Confirm the reporting context. The saved record cannot be "
                "edited or replaced after generation."
            ),
        )

        st.info(
            "Creating a snapshot does not modify operational reports. It "
            "preserves a new immutable copy of the selected reporting view."
        )

        generation_token_key = "report_generation_token"
        if generation_token_key not in st.session_state:
            st.session_state[
                generation_token_key
            ] = str(uuid4())

        confirmation = st.checkbox(
            "I reviewed the active event, SitRep number, and report mode."
        )

        if st.button(
            "Create Immutable Snapshot",
            type="primary",
            width="stretch",
            disabled=not confirmation,
        ):
            try:
                snapshot_id = create_report_snapshot(
                    report_mode=report_mode,
                    generation_key=st.session_state[
                        generation_token_key
                    ],
                    generator_user_id=current_user.id,
                )
            except (
                DuplicateReportGenerationError,
                NoActiveEventForReportError,
                ReportAuthorizationError,
                ReportDataIntegrityError,
                ReportValidationError,
                ReportServiceError,
            ) as error:
                st.error(str(error))
            except Exception:
                st.error(
                    "The report snapshot could not be generated. "
                    "No existing report snapshot was modified."
                )
            else:
                st.session_state[
                    generation_token_key
                ] = str(uuid4())
                st.session_state[
                    "selected_report_snapshot_id"
                ] = snapshot_id
                st.session_state[
                    "report_success"
                ] = (
                    f"Situation-report snapshot #{snapshot_id} "
                    "was generated successfully."
                )
                st.rerun()

with archive_tab:
    render_dashboard_section_header(
        title="Snapshot Archive",
        subtitle=(
            "Scan saved situation reports by event, mode, SitRep, generator, "
            "and integrity reference."
        ),
    )

    if not snapshot_rows:
        st.info(
            "No report snapshots have been generated yet."
        )
    else:
        archive_rows = [
            {
                "Snapshot": f"#{int(row['id'])}",
                "Event": display_event_name(row),
                "SitRep": display_sitrep(
                    row["sitrep_number"]
                ),
                "Mode": row["report_mode"],
                "Generated": format_datetime(
                    row["generated_at"]
                ),
                "Integrity": compact_integrity_hash(
                    row["snapshot_sha256"]
                ),
                "Generated By": row["generated_by"],
            }
            for row in snapshot_rows
        ]

        st.dataframe(
            pd.DataFrame(archive_rows),
            width="stretch",
            hide_index=True,
            column_config={
                "Snapshot": st.column_config.TextColumn(
                    "Snapshot",
                    width=70,
                    pinned=True,
                ),
                "Event": st.column_config.TextColumn(
                    "Event",
                    width=180,
                ),
                "SitRep": st.column_config.TextColumn(
                    "SitRep",
                    width=110,
                ),
                "Mode": st.column_config.TextColumn(
                    "Mode",
                    width=110,
                ),
                "Generated": st.column_config.TextColumn(
                    "Generated",
                    width=140,
                ),
                "Integrity": st.column_config.TextColumn(
                    "Integrity",
                    width=100,
                ),
                "Generated By": st.column_config.TextColumn(
                    "Generated By",
                    width=160,
                ),
            },
        )

        st.caption(
            "The archive shows a shortened integrity reference for routine "
            "scanning. Review & Export displays the complete SHA-256 value."
        )

with export_tab:
    render_dashboard_section_header(
        title="Review & Export Snapshot",
        subtitle=(
            "Select an immutable snapshot, verify its recorded context, and "
            "download the Excel or PDF representation."
        ),
    )

    if not snapshot_rows:
        st.info(
            "No saved snapshot is available for export."
        )
    else:
        snapshot_by_id = {
            int(row["id"]): row
            for row in snapshot_rows
        }
        snapshot_ids = list(snapshot_by_id)
        selected_default = st.session_state.get(
            "selected_report_snapshot_id"
        )

        if selected_default in snapshot_by_id:
            default_index = snapshot_ids.index(
                int(selected_default)
            )
        else:
            default_index = 0

        selected_snapshot_id = st.selectbox(
            "Saved snapshot",
            options=snapshot_ids,
            index=default_index,
            format_func=lambda snapshot_id: (
                f"#{snapshot_id} — "
                f"{display_event_name(snapshot_by_id[snapshot_id])} — "
                f"{snapshot_by_id[snapshot_id]['report_mode']}"
            ),
        )

        try:
            selected_snapshot = get_report_snapshot(
                snapshot_id=int(selected_snapshot_id)
            )
        except ReportServiceError as error:
            st.error(str(error))
        else:
            snapshot_payload = selected_snapshot["snapshot_json"]
            snapshot_event = snapshot_payload.get("event", {})

            st.markdown(
                "### "
                f"Snapshot #{int(selected_snapshot['id'])} — "
                f"{display_event_name(snapshot_event)}"
            )

            render_kpi_grid(
                [
                    {
                        "label": "Mode",
                        "value": str(
                            selected_snapshot["report_mode"]
                        ),
                    },
                    {
                        "label": "SitRep",
                        "value": display_sitrep(
                            selected_snapshot["sitrep_number"]
                        ),
                    },
                    {
                        "label": "Generated",
                        "value": format_datetime(
                            selected_snapshot["generated_at"]
                        ),
                    },
                    {
                        "label": "Report Type",
                        "value": str(
                            selected_snapshot["report_type"]
                        ),
                    },
                ],
            )

            st.write(
                "**Generated by:**",
                selected_snapshot["generated_by"],
            )
            st.caption("SHA-256 integrity hash")
            st.code(
                str(selected_snapshot["snapshot_sha256"]),
                language=None,
            )

            st.info(
                "Saved snapshots are append-only. They cannot be edited or "
                "deleted through the application. If operational data "
                "changes, generate a new snapshot instead."
            )

            try:
                export_bundle = get_report_export_bundle(
                    selected_snapshot,
                    st.session_state,
                )
                excel_bytes = export_bundle.excel_bytes
                pdf_bytes = export_bundle.pdf_bytes
            except (
                ExportServiceError,
                ReportExportCacheError,
            ) as error:
                st.error(str(error))
            else:
                export_columns = st.columns(2)

                with export_columns[0]:
                    st.download_button(
                        "Download Excel Workbook",
                        data=excel_bytes,
                        file_name=report_filename(
                            selected_snapshot,
                            extension="xlsx",
                        ),
                        mime=(
                            "application/vnd.openxmlformats-officedocument."
                            "spreadsheetml.sheet"
                        ),
                        width="stretch",
                    )

                with export_columns[1]:
                    st.download_button(
                        "Download PDF SitRep",
                        data=pdf_bytes,
                        file_name=report_filename(
                            selected_snapshot,
                            extension="pdf",
                        ),
                        mime="application/pdf",
                        width="stretch",
                    )
