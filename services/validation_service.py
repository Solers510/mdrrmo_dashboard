from datetime import datetime
from zoneinfo import ZoneInfo

from database.connection import SessionLocal, session_scope
from database.repositories import (
    fetch_active_event_rows,
    fetch_barangay_update_for_review,
    fetch_barangay_validation_queue,
)


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")


class ValidationServiceError(Exception):
    """Base exception for validation operations."""


class ValidationInputError(ValidationServiceError):
    """Raised when review information is invalid."""


class ValidationDataIntegrityError(ValidationServiceError):
    """Raised when operational data is inconsistent."""


class ReportAlreadyReviewedError(ValidationServiceError):
    """Raised when the report is no longer pending review."""


def get_barangay_validation_queue() -> list[dict[str, object]]:
    """
    Retrieve submitted barangay reports for the active event.
    """
    try:
        with SessionLocal() as session:
            active_events = fetch_active_event_rows(
                session
            )

            if len(active_events) > 1:
                raise ValidationDataIntegrityError(
                    "More than one active disaster event exists."
                )

            if not active_events:
                return []

            event_id = int(
                active_events[0]["id"]
            )

            rows = fetch_barangay_validation_queue(
                session,
                event_id=event_id,
            )

            return [
                dict(row)
                for row in rows
            ]

    except ValidationServiceError:
        raise

    except Exception as error:
        raise ValidationServiceError(
            "The validation queue could not be loaded."
        ) from error


def review_barangay_update(
    *,
    update_id: int,
    decision: str,
    reviewed_by: str,
    review_notes: str | None,
) -> None:
    """
    Mark a submitted report as Validated or
    Needs Correction.
    """
    cleaned_reviewer = reviewed_by.strip()

    cleaned_notes = (
        review_notes.strip()
        if review_notes and review_notes.strip()
        else None
    )

    allowed_decisions = {
        "Validated",
        "Needs Correction",
    }

    if update_id <= 0:
        raise ValidationInputError(
            "A valid report must be selected."
        )

    if decision not in allowed_decisions:
        raise ValidationInputError(
            "The selected review decision is invalid."
        )

    if not cleaned_reviewer:
        raise ValidationInputError(
            "Reviewer name is required."
        )

    if (
        decision == "Needs Correction"
        and not cleaned_notes
    ):
        raise ValidationInputError(
            "Correction instructions are required when "
            "marking a report as Needs Correction."
        )

    with session_scope() as session:
        active_events = fetch_active_event_rows(
            session
        )

        if len(active_events) > 1:
            raise ValidationDataIntegrityError(
                "More than one active disaster event exists."
            )

        if not active_events:
            raise ValidationInputError(
                "No active disaster event exists."
            )

        active_event_id = int(
            active_events[0]["id"]
        )

        report = fetch_barangay_update_for_review(
            session,
            update_id=update_id,
        )

        if report is None:
            raise ValidationInputError(
                "The selected barangay report does not exist."
            )

        if report.event_id != active_event_id:
            raise ValidationInputError(
                "The selected report does not belong to "
                "the active disaster event."
            )

        allowed_current_statuses = {
            "Submitted",
            "For Validation",
        }

        if (
            report.validation_status
            not in allowed_current_statuses
        ):
            raise ReportAlreadyReviewedError(
                "This report has already been reviewed."
            )

        report.validation_status = decision
        report.reviewed_by = cleaned_reviewer
        report.review_notes = cleaned_notes
        report.reviewed_at = datetime.now(
            MANILA_TIMEZONE
        )

        session.flush()