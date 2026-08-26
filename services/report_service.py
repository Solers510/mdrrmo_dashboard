from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import json
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from config.access_control import (
    PERMISSION_VIEW_REPORTS,
    permissions_for_role,
)
from database.connection import SessionLocal, session_scope
from database.models import ReportSnapshot
from database.repositories import (
    fetch_active_event_rows,
    fetch_app_user_by_id,
    fetch_recent_incidents,
    fetch_recent_report_snapshots,
    fetch_report_snapshot_by_generation_key,
    fetch_report_snapshot_by_id,
)
from services.dashboard_service import (
    DashboardServiceError,
    get_dashboard_bundle,
)


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

REPORT_TYPE_SITREP = "Situation Report"
REPORT_MODE_PROVISIONAL = "Provisional Operational"
REPORT_MODE_OFFICIAL = "Official Validated"
REPORT_MODES = (
    REPORT_MODE_PROVISIONAL,
    REPORT_MODE_OFFICIAL,
)


class ReportServiceError(Exception):
    """Base exception for situation-report operations."""


class ReportAuthorizationError(ReportServiceError):
    """Raised when the account cannot generate or view reports."""


class ReportValidationError(ReportServiceError):
    """Raised when report-generation input is invalid."""


class ReportDataIntegrityError(ReportServiceError):
    """Raised when the operational database is inconsistent."""


class DuplicateReportGenerationError(ReportServiceError):
    """Raised when the same generation request is submitted twice."""


class NoActiveEventForReportError(ReportServiceError):
    """Raised when no active event exists for a new report."""


def _plain(value: Any) -> Any:
    """Convert database values into stable JSON-compatible values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(key): _plain(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _plain(item)
            for item in value
        ]

    if hasattr(value, "_mapping"):
        return _plain(dict(value._mapping))

    return str(value)


def canonical_snapshot_json(snapshot: dict[str, object]) -> str:
    return json.dumps(
        _plain(snapshot),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def snapshot_sha256(snapshot: dict[str, object]) -> str:
    return hashlib.sha256(
        canonical_snapshot_json(snapshot).encode("utf-8")
    ).hexdigest()


def _validate_generation_key(value: str) -> str:
    cleaned = value.strip()

    try:
        parsed = UUID(cleaned)
    except (ValueError, AttributeError) as error:
        raise ReportValidationError(
            "The report generation token is invalid. Refresh the page and try again."
        ) from error

    return str(parsed)


def _require_report_user(session, *, user_id: int):
    user = fetch_app_user_by_id(
        session,
        user_id=user_id,
    )

    if user is None or not user.is_active:
        raise ReportAuthorizationError(
            "Your application account is not active."
        )

    if (
        PERMISSION_VIEW_REPORTS
        not in permissions_for_role(user.role)
    ):
        raise ReportAuthorizationError(
            "Your account is not authorized to generate reports."
        )

    return user


def _generator_snapshot(user) -> str:
    return f"{user.display_name} - {user.role}"


def get_current_report_event() -> dict[str, object] | None:
    try:
        with SessionLocal() as session:
            rows = fetch_active_event_rows(session)

            if len(rows) > 1:
                raise ReportDataIntegrityError(
                    "More than one active disaster event exists."
                )

            if not rows:
                return None

            return dict(rows[0])

    except ReportServiceError:
        raise
    except Exception as error:
        raise ReportServiceError(
            "The active event could not be loaded for reporting."
        ) from error


def _select_dashboard_payload(
    dashboard: dict[str, object],
    report_mode: str,
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    dict[str, object],
    list[dict[str, object]],
]:
    if report_mode == REPORT_MODE_PROVISIONAL:
        return (
            dashboard["provisional_summary"],
            dashboard["provisional_rows"],
            dashboard["provisional_evacuation_summary"],
            dashboard["provisional_evacuation_rows"],
        )

    if report_mode == REPORT_MODE_OFFICIAL:
        return (
            dashboard["official_summary"],
            dashboard["official_rows"],
            dashboard["official_evacuation_summary"],
            dashboard["official_evacuation_rows"],
        )

    raise ReportValidationError(
        "Select a valid report mode."
    )


def _select_reconciliation_payload(
    dashboard: dict[str, object],
    report_mode: str,
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    bool,
]:
    if report_mode == REPORT_MODE_PROVISIONAL:
        prefix = "provisional"
    elif report_mode == REPORT_MODE_OFFICIAL:
        prefix = "official"
    else:
        raise ReportValidationError(
            "Select a valid report mode."
        )

    return (
        dashboard.get(
            f"{prefix}_reconciliation_summary",
            dashboard.get("reconciliation_summary", {}),
        ),
        dashboard.get(
            f"{prefix}_reconciliation_rows",
            dashboard.get("reconciliation_rows", []),
        ),
        bool(
            dashboard.get(
                f"{prefix}_reconciliation_available",
                dashboard.get("reconciliation_available", False),
            )
        ),
    )


def create_report_snapshot(
    *,
    report_mode: str,
    generation_key: str,
    generator_user_id: int,
) -> int:
    if report_mode not in REPORT_MODES:
        raise ReportValidationError(
            "Select a valid report mode."
        )

    canonical_key = _validate_generation_key(
        generation_key
    )

    try:
        dashboard = get_dashboard_bundle()
    except DashboardServiceError as error:
        raise ReportServiceError(
            "The operational data could not be prepared for reporting."
        ) from error

    active_event = dashboard.get("active_event")

    if active_event is None:
        raise NoActiveEventForReportError(
            "No active disaster event exists."
        )

    (
        population_summary,
        barangay_rows,
        evacuation_summary,
        evacuation_rows,
    ) = _select_dashboard_payload(
        dashboard,
        report_mode,
    )
    (
        reconciliation_summary,
        reconciliation_rows,
        reconciliation_available,
    ) = _select_reconciliation_payload(
        dashboard,
        report_mode,
    )

    generated_at = datetime.now(
        MANILA_TIMEZONE
    )
    event_id = int(
        active_event["id"]
    )

    try:
        with session_scope() as session:
            generator = _require_report_user(
                session,
                user_id=generator_user_id,
            )

            existing = fetch_report_snapshot_by_generation_key(
                session,
                generation_key=canonical_key,
            )

            if existing is not None:
                raise DuplicateReportGenerationError(
                    "This report-generation request was already saved. "
                    "The duplicate request was ignored."
                )

            current_events = fetch_active_event_rows(
                session
            )

            if len(current_events) != 1:
                raise ReportDataIntegrityError(
                    "The active event changed while the report was being generated."
                )

            if int(current_events[0]["id"]) != event_id:
                raise ReportDataIntegrityError(
                    "The active event changed while the report was being generated."
                )

            incidents = [
                dict(row)
                for row in fetch_recent_incidents(
                    session,
                    event_id=event_id,
                    limit=1000,
                )
            ]

            if report_mode == REPORT_MODE_OFFICIAL:
                incidents = [
                    row
                    for row in incidents
                    if row.get("validation_status") == "Validated"
                ]

            generator_text = _generator_snapshot(
                generator
            )

            snapshot: dict[str, object] = {
                "schema_version": 1,
                "report_type": REPORT_TYPE_SITREP,
                "report_mode": report_mode,
                "generated_at": generated_at,
                "generated_by": generator_text,
                "event": dict(active_event),
                "population_summary": population_summary,
                "barangays": barangay_rows,
                "evacuation_summary": evacuation_summary,
                "evacuation_centers": evacuation_rows,
                "reconciliation_summary": reconciliation_summary,
                "reconciliation": reconciliation_rows,
                "reconciliation_available": reconciliation_available,
                "incidents": incidents,
            }

            plain_snapshot = _plain(
                snapshot
            )
            digest = snapshot_sha256(
                plain_snapshot
            )

            record = ReportSnapshot(
                event_id=event_id,
                generation_key=canonical_key,
                report_type=REPORT_TYPE_SITREP,
                report_mode=report_mode,
                sitrep_number=(
                    str(
                        active_event.get(
                            "current_sitrep_number"
                        )
                    ).strip()
                    if active_event.get(
                        "current_sitrep_number"
                    )
                    else None
                ),
                generated_by_user_id=generator.id,
                generated_by=generator_text,
                generated_at=generated_at,
                snapshot_json=plain_snapshot,
                snapshot_sha256=digest,
            )

            session.add(record)
            session.flush()

            return int(record.id)

    except IntegrityError as error:
        message = str(error.orig)

        if "uq_report_snapshots_generation_key" in message:
            raise DuplicateReportGenerationError(
                "This report-generation request was already saved. "
                "The duplicate request was ignored."
            ) from error

        raise ReportServiceError(
            "The report snapshot could not be saved."
        ) from error

    except ReportServiceError:
        raise

    except Exception as error:
        raise ReportServiceError(
            "The report snapshot could not be generated."
        ) from error


def list_report_snapshots(
    *,
    limit: int = 100,
) -> list[dict[str, object]]:
    try:
        with SessionLocal() as session:
            return [
                dict(row)
                for row in fetch_recent_report_snapshots(
                    session,
                    limit=limit,
                )
            ]
    except Exception as error:
        raise ReportServiceError(
            "Saved report snapshots could not be loaded."
        ) from error


def get_report_snapshot(
    *,
    snapshot_id: int,
) -> dict[str, object]:
    try:
        with SessionLocal() as session:
            record = fetch_report_snapshot_by_id(
                session,
                snapshot_id=snapshot_id,
            )

            if record is None:
                raise ReportValidationError(
                    "The selected report snapshot does not exist."
                )

            snapshot = _plain(
                record.snapshot_json
            )
            calculated_hash = snapshot_sha256(
                snapshot
            )

            if calculated_hash != record.snapshot_sha256:
                raise ReportDataIntegrityError(
                    "The stored report snapshot failed its integrity check."
                )

            return {
                "id": int(record.id),
                "event_id": int(record.event_id),
                "generation_key": record.generation_key,
                "report_type": record.report_type,
                "report_mode": record.report_mode,
                "sitrep_number": record.sitrep_number,
                "generated_by_user_id": record.generated_by_user_id,
                "generated_by": record.generated_by,
                "generated_at": record.generated_at,
                "snapshot_sha256": record.snapshot_sha256,
                "snapshot_json": snapshot,
            }

    except ReportServiceError:
        raise
    except Exception as error:
        raise ReportServiceError(
            "The selected report snapshot could not be loaded."
        ) from error
