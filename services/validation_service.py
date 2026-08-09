from datetime import datetime
from zoneinfo import ZoneInfo

from config.access_control import (
    PERMISSION_VALIDATE_BARANGAY_REPORTS,
    permissions_for_role,
)
from database.connection import SessionLocal, session_scope
from database.repositories import (
    fetch_active_barangays,
    fetch_active_event_rows,
    fetch_app_user_by_id,
    fetch_barangay_update_for_review,
    fetch_barangay_validation_queue,
    fetch_evacuation_update_for_review,
    fetch_evacuation_validation_queue,
    fetch_latest_barangay_update_for_barangay,
    fetch_latest_evacuation_updates_for_barangay,
)


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")

PENDING_REVIEW_STATUSES = {
    "Submitted",
    "For Validation",
}

RECONCILIATION_SOURCE_STATUSES = (
    "Submitted",
    "For Validation",
    "Validated",
    "Needs Correction",
)

ACTIVE_CENTER_STATUSES = {
    "Open",
    "Full",
    "Over Capacity",
}


class ValidationServiceError(Exception):
    """Base exception for validation operations."""


class ValidationInputError(ValidationServiceError):
    """Raised when review information is invalid."""


class ValidationAuthorizationError(ValidationServiceError):
    """Raised when the reviewer lacks authorization."""


class ValidationDataIntegrityError(ValidationServiceError):
    """Raised when operational data is inconsistent."""


class ReportAlreadyReviewedError(ValidationServiceError):
    """Raised when a report is no longer pending."""


def validate_review_decision(
    *,
    decision: str,
    review_notes: str | None,
) -> str | None:
    """Validate a review decision without touching the database."""
    if decision not in {"Validated", "Needs Correction"}:
        raise ValidationInputError(
            "The selected review decision is invalid."
        )

    cleaned_notes = (
        review_notes.strip()
        if review_notes and review_notes.strip()
        else None
    )

    if decision == "Needs Correction" and not cleaned_notes:
        raise ValidationInputError(
            "Correction instructions are required when marking "
            "a report as Needs Correction."
        )

    return cleaned_notes


def _active_event_id(session) -> int | None:
    rows = fetch_active_event_rows(session)

    if len(rows) > 1:
        raise ValidationDataIntegrityError(
            "More than one active disaster event exists."
        )

    if not rows:
        return None

    return int(rows[0]["id"])


def _require_reviewer(session, *, reviewer_user_id: int):
    if reviewer_user_id <= 0:
        raise ValidationAuthorizationError(
            "A valid reviewer identity is required."
        )

    reviewer = fetch_app_user_by_id(
        session,
        user_id=reviewer_user_id,
    )

    if reviewer is None:
        raise ValidationAuthorizationError(
            "The reviewer account does not exist."
        )

    if not reviewer.is_active:
        raise ValidationAuthorizationError(
            "The reviewer account is inactive."
        )

    if (
        PERMISSION_VALIDATE_BARANGAY_REPORTS
        not in permissions_for_role(reviewer.role)
    ):
        raise ValidationAuthorizationError(
            "This account is not authorized to validate "
            "operational reports."
        )

    return reviewer


def _reviewer_snapshot(reviewer) -> str:
    return f"{reviewer.display_name} — {reviewer.role}"


def get_barangay_validation_queue() -> list[dict[str, object]]:
    try:
        with SessionLocal() as session:
            event_id = _active_event_id(session)
            if event_id is None:
                return []

            return [
                dict(row)
                for row in fetch_barangay_validation_queue(
                    session,
                    event_id=event_id,
                )
            ]
    except ValidationServiceError:
        raise
    except Exception as error:
        raise ValidationServiceError(
            "The barangay validation queue could not be loaded."
        ) from error


def get_evacuation_validation_queue() -> list[dict[str, object]]:
    try:
        with SessionLocal() as session:
            event_id = _active_event_id(session)
            if event_id is None:
                return []

            return [
                dict(row)
                for row in fetch_evacuation_validation_queue(
                    session,
                    event_id=event_id,
                )
            ]
    except ValidationServiceError:
        raise
    except Exception as error:
        raise ValidationServiceError(
            "The evacuation-center validation queue could not be loaded."
        ) from error


def get_population_reconciliation_queue() -> list[dict[str, object]]:
    try:
        with SessionLocal() as session:
            event_id = _active_event_id(session)
            if event_id is None:
                return []

            results: list[dict[str, object]] = []

            for barangay in fetch_active_barangays(session):
                barangay_id = int(barangay["id"])

                report = fetch_latest_barangay_update_for_barangay(
                    session,
                    event_id=event_id,
                    barangay_id=barangay_id,
                    included_statuses=RECONCILIATION_SOURCE_STATUSES,
                )

                ec_rows = fetch_latest_evacuation_updates_for_barangay(
                    session,
                    event_id=event_id,
                    barangay_id=barangay_id,
                    included_statuses=RECONCILIATION_SOURCE_STATUSES,
                )

                active_ec_rows = [
                    row
                    for row in ec_rows
                    if row["status"] in ACTIVE_CENTER_STATUSES
                ]

                ec_families = sum(
                    int(row["families"])
                    for row in active_ec_rows
                )
                ec_individuals = sum(
                    int(row["individuals"])
                    for row in active_ec_rows
                )

                ec_times = [
                    row["recorded_at"]
                    for row in ec_rows
                    if row["recorded_at"] is not None
                ]
                latest_ec_at = max(ec_times) if ec_times else None

                if report is None:
                    reconciliation_status = (
                        "No Barangay Report"
                        if ec_rows
                        else "No Current Data"
                    )
                    barangay_families = None
                    barangay_individuals = None
                    barangay_status = None
                    barangay_recorded_at = None
                    family_difference = None
                    individual_difference = None
                else:
                    barangay_families = int(
                        report.inside_ec_families
                    )
                    barangay_individuals = int(
                        report.inside_ec_individuals
                    )
                    barangay_status = report.validation_status
                    barangay_recorded_at = report.recorded_at
                    family_difference = (
                        barangay_families - ec_families
                    )
                    individual_difference = (
                        barangay_individuals - ec_individuals
                    )

                    if not ec_rows:
                        reconciliation_status = (
                            "No EC Report"
                            if (
                                barangay_families > 0
                                or barangay_individuals > 0
                            )
                            else "Match"
                        )
                    elif (
                        family_difference == 0
                        and individual_difference == 0
                    ):
                        reconciliation_status = "Match"
                    else:
                        reconciliation_status = "Mismatch"

                results.append(
                    {
                        "barangay_id": barangay_id,
                        "barangay_name": barangay["name"],
                        "barangay_inside_families": barangay_families,
                        "barangay_inside_individuals": barangay_individuals,
                        "barangay_validation_status": barangay_status,
                        "barangay_recorded_at": barangay_recorded_at,
                        "ec_inside_families": ec_families,
                        "ec_inside_individuals": ec_individuals,
                        "ec_operational_centers": len(active_ec_rows),
                        "latest_ec_recorded_at": latest_ec_at,
                        "family_difference": family_difference,
                        "individual_difference": individual_difference,
                        "reconciliation_status": reconciliation_status,
                    }
                )

            return results
    except ValidationServiceError:
        raise
    except Exception as error:
        raise ValidationServiceError(
            "Population reconciliation could not be loaded."
        ) from error


def review_barangay_update(
    *,
    update_id: int,
    decision: str,
    reviewer_user_id: int,
    review_notes: str | None,
) -> None:
    if update_id <= 0:
        raise ValidationInputError(
            "A valid barangay report must be selected."
        )

    cleaned_notes = validate_review_decision(
        decision=decision,
        review_notes=review_notes,
    )

    with session_scope() as session:
        reviewer = _require_reviewer(
            session,
            reviewer_user_id=reviewer_user_id,
        )

        event_id = _active_event_id(session)
        if event_id is None:
            raise ValidationInputError(
                "No active disaster event exists."
            )

        report = fetch_barangay_update_for_review(
            session,
            update_id=update_id,
        )

        if report is None:
            raise ValidationInputError(
                "The selected barangay report does not exist."
            )

        if int(report.event_id) != event_id:
            raise ValidationInputError(
                "The selected report does not belong to the active event."
            )

        if report.validation_status not in PENDING_REVIEW_STATUSES:
            raise ReportAlreadyReviewedError(
                "This barangay report has already been reviewed."
            )

        report.validation_status = decision
        report.reviewed_by_user_id = reviewer.id
        report.reviewed_by = _reviewer_snapshot(reviewer)
        report.review_notes = cleaned_notes
        report.reviewed_at = datetime.now(MANILA_TIMEZONE)
        session.flush()


def review_evacuation_update(
    *,
    update_id: int,
    decision: str,
    reviewer_user_id: int,
    review_notes: str | None,
) -> None:
    if update_id <= 0:
        raise ValidationInputError(
            "A valid evacuation-center report must be selected."
        )

    cleaned_notes = validate_review_decision(
        decision=decision,
        review_notes=review_notes,
    )

    with session_scope() as session:
        reviewer = _require_reviewer(
            session,
            reviewer_user_id=reviewer_user_id,
        )

        event_id = _active_event_id(session)
        if event_id is None:
            raise ValidationInputError(
                "No active disaster event exists."
            )

        report = fetch_evacuation_update_for_review(
            session,
            update_id=update_id,
        )

        if report is None:
            raise ValidationInputError(
                "The selected evacuation-center report does not exist."
            )

        if int(report.event_id) != event_id:
            raise ValidationInputError(
                "The selected report does not belong to the active event."
            )

        if report.validation_status not in PENDING_REVIEW_STATUSES:
            raise ReportAlreadyReviewedError(
                "This evacuation-center report has already been reviewed."
            )

        report.validation_status = decision
        report.reviewed_by_user_id = reviewer.id
        report.reviewed_by = _reviewer_snapshot(reviewer)
        report.review_notes = cleaned_notes
        report.reviewed_at = datetime.now(MANILA_TIMEZONE)
        session.flush()
