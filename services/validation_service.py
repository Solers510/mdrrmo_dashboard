from datetime import datetime
from zoneinfo import ZoneInfo

from config.access_control import (
    PERMISSION_VALIDATE_BARANGAY_REPORTS,
    permissions_for_role,
)
from database.connection import (
    SessionLocal,
    session_scope,
)
from database.repositories import (
    fetch_active_event_rows,
    fetch_app_user_by_id,
    fetch_barangay_update_for_review,
    fetch_barangay_validation_queue,
)


MANILA_TIMEZONE = ZoneInfo("Asia/Manila")


class ValidationServiceError(Exception):
    """Base exception for validation operations."""


class ValidationInputError(ValidationServiceError):
    """Raised when review information is invalid."""


class ValidationAuthorizationError(
    ValidationServiceError
):
    """Raised when the reviewer lacks authorization."""


class ValidationDataIntegrityError(
    ValidationServiceError
):
    """Raised when operational data is inconsistent."""


class ReportAlreadyReviewedError(
    ValidationServiceError
):
    """Raised when a report is no longer pending."""


def get_barangay_validation_queue(
) -> list[dict[str, object]]:
    """
    Retrieve submitted reports for the active event.
    """
    try:
        with SessionLocal() as session:
            active_events = fetch_active_event_rows(
                session
            )

            if len(active_events) > 1:
                raise ValidationDataIntegrityError(
                    "More than one active disaster "
                    "event exists."
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
    reviewer_user_id: int,
    review_notes: str | None,
) -> None:
    """
    Review a barangay report using an authenticated
    application-user identity.
    """
    allowed_decisions = {
        "Validated",
        "Needs Correction",
    }

    if update_id <= 0:
        raise ValidationInputError(
            "A valid report must be selected."
        )

    if reviewer_user_id <= 0:
        raise ValidationAuthorizationError(
            "A valid reviewer identity is required."
        )

    if decision not in allowed_decisions:
        raise ValidationInputError(
            "The selected review decision is invalid."
        )

    cleaned_notes = (
        review_notes.strip()
        if review_notes
        and review_notes.strip()
        else None
    )

    if (
        decision == "Needs Correction"
        and not cleaned_notes
    ):
        raise ValidationInputError(
            "Correction instructions are required "
            "when marking a report as Needs Correction."
        )

    with session_scope() as session:
        # -------------------------------------------------
        # VERIFY REVIEWER
        # -------------------------------------------------

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

        reviewer_permissions = (
            permissions_for_role(
                reviewer.role
            )
        )

        if (
            PERMISSION_VALIDATE_BARANGAY_REPORTS
            not in reviewer_permissions
        ):
            raise ValidationAuthorizationError(
                "This account is not authorized "
                "to validate barangay reports."
            )

        # -------------------------------------------------
        # VERIFY EVENT
        # -------------------------------------------------

        active_events = fetch_active_event_rows(
            session
        )

        if len(active_events) > 1:
            raise ValidationDataIntegrityError(
                "More than one active disaster "
                "event exists."
            )

        if not active_events:
            raise ValidationInputError(
                "No active disaster event exists."
            )

        active_event_id = int(
            active_events[0]["id"]
        )

        # -------------------------------------------------
        # LOCK AND VERIFY REPORT
        # -------------------------------------------------

        report = fetch_barangay_update_for_review(
            session,
            update_id=update_id,
        )

        if report is None:
            raise ValidationInputError(
                "The selected barangay report "
                "does not exist."
            )

        if report.event_id != active_event_id:
            raise ValidationInputError(
                "The selected report does not belong "
                "to the active disaster event."
            )

        if report.validation_status not in {
            "Submitted",
            "For Validation",
        }:
            raise ReportAlreadyReviewedError(
                "This report has already been reviewed."
            )

        # -------------------------------------------------
        # SAVE AUTHENTICATED REVIEW
        # -------------------------------------------------

        report.validation_status = decision

        report.reviewed_by_user_id = (
            reviewer.id
        )

        report.reviewed_by = (
            f"{reviewer.display_name} — "
            f"{reviewer.role}"
        )

        report.review_notes = cleaned_notes

        report.reviewed_at = datetime.now(
            MANILA_TIMEZONE
        )

        session.flush()