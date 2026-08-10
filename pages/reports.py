from uuid import uuid4

import pandas as pd
import streamlit as st

from config.access_control import (
    PERMISSION_VIEW_REPORTS,
)
from services.export_service import (
    ExportServiceError,
    build_excel_report,
    build_pdf_report,
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


current_user = require_permission(
    PERMISSION_VIEW_REPORTS
)

st.title("Reports and Exports")
st.caption(
    "Generate immutable situation-report snapshots and export exactly "
    "what was recorded at the time of generation."
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

st.subheader("Generate New Situation Report Snapshot")

if active_event is None:
    st.info(
        "No active disaster event exists. Saved historical report "
        "snapshots remain available below."
    )
else:
    event_name = str(
        active_event["event_name"]
    )
    classification = active_event.get(
        "classification"
    )

    if classification:
        event_name = f"{classification} {event_name}"

    event_columns = st.columns(4)
    event_columns[0].metric(
        "Active Event",
        event_name,
    )
    event_columns[1].metric(
        "Alert Level",
        str(active_event["alert_code"]),
    )
    event_columns[2].metric(
        "EOC Status",
        str(active_event["eoc_status"]),
    )
    event_columns[3].metric(
        "SitRep",
        str(
            active_event.get(
                "current_sitrep_number"
            )
            or "Not set"
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
            "This snapshot uses validated barangay and evacuation-center "
            "source reports for its official totals."
        )

    generation_token_key = "report_generation_token"
    if generation_token_key not in st.session_state:
        st.session_state[
            generation_token_key
        ] = str(uuid4())

    confirmation = st.checkbox(
        "I reviewed the active event, SitRep number, and selected report mode."
    )

    if st.button(
        "Create Report Snapshot",
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

st.divider()
st.subheader("Saved Report Snapshots")

if not snapshot_rows:
    st.info(
        "No report snapshots have been generated yet."
    )
    st.stop()

history_table = pd.DataFrame(
    [
        {
            "Snapshot ID": row["id"],
            "Event": row["event_name"],
            "Classification": row["classification"],
            "SitRep": row["sitrep_number"],
            "Mode": row["report_mode"],
            "Generated By": row["generated_by"],
            "Generated At": row["generated_at"],
            "SHA-256": row["snapshot_sha256"],
        }
        for row in snapshot_rows
    ]
)

st.dataframe(
    history_table,
    width="stretch",
    hide_index=True,
)

snapshot_by_id = {
    int(row["id"]): row
    for row in snapshot_rows
}

snapshot_ids = list(
    snapshot_by_id
)

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
    "Select saved snapshot",
    options=snapshot_ids,
    index=default_index,
    format_func=lambda snapshot_id: (
        f"#{snapshot_id} - "
        f"{snapshot_by_id[snapshot_id]['event_name']} - "
        f"{snapshot_by_id[snapshot_id]['report_mode']}"
    ),
)

try:
    selected_snapshot = get_report_snapshot(
        snapshot_id=int(selected_snapshot_id)
    )
except ReportServiceError as error:
    st.error(str(error))
    st.stop()

metadata_columns = st.columns(4)
metadata_columns[0].metric(
    "Snapshot ID",
    int(selected_snapshot["id"]),
)
metadata_columns[1].metric(
    "Mode",
    str(selected_snapshot["report_mode"]),
)
metadata_columns[2].metric(
    "SitRep",
    str(selected_snapshot["sitrep_number"] or "Not set"),
)
metadata_columns[3].metric(
    "Generated By",
    str(selected_snapshot["generated_by"]),
)

st.caption(
    "Integrity hash: "
    + str(
        selected_snapshot[
            "snapshot_sha256"
        ]
    )
)

st.info(
    "Saved snapshots are append-only. They cannot be edited or deleted "
    "through the application. If operational data changes, generate a "
    "new snapshot instead."
)

try:
    excel_bytes = build_excel_report(
        selected_snapshot
    )
    pdf_bytes = build_pdf_report(
        selected_snapshot
    )
except ExportServiceError as error:
    st.error(str(error))
    st.stop()

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
