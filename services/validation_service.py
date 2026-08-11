from collections import defaultdict
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
    fetch_latest_barangay_updates_for_event,
    fetch_latest_cross_allocations_for_event,
    fetch_latest_evacuation_updates_for_event,
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
    if decision not in {"Validated", "Needs Correction"}:
        raise ValidationInputError(
            "The selected review decision is invalid."
        )

    cleaned_notes = (
        review_notes.strip()
        if review_notes and review_notes.strip()
        else None
    )

    if (
        decision == "Needs Correction"
        and not cleaned_notes
    ):
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


def _require_reviewer(
    session,
    *,
    reviewer_user_id: int,
):
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


def get_barangay_validation_queue(
) -> list[dict[str, object]]:
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


def get_evacuation_validation_queue(
) -> list[dict[str, object]]:
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


def get_population_reconciliation_queue(
) -> list[dict[str, object]]:
    """
    Reconcile barangay Inside-EC counts with attributed EC occupancy.

    Normally, an EC's occupants are attributed to its home barangay.
    Cross-barangay allocation snapshots subtract foreign-origin evacuees
    from the host barangay and add them to their origin barangay.
    """
    try:
        with SessionLocal() as session:
            event_id = _active_event_id(session)
            if event_id is None:
                return []

            barangays = [
                dict(row)
                for row in fetch_active_barangays(session)
            ]

            latest_ec_rows = [
                dict(row)
                for row in fetch_latest_evacuation_updates_for_event(
                    session,
                    event_id=event_id,
                    included_statuses=RECONCILIATION_SOURCE_STATUSES,
                )
            ]

            allocation_rows = [
                dict(row)
                for row in fetch_latest_cross_allocations_for_event(
                    session,
                    event_id=event_id,
                )
            ]

            latest_barangay_rows = [
                dict(row)
                for row in fetch_latest_barangay_updates_for_event(
                    session,
                    event_id=event_id,
                    included_statuses=RECONCILIATION_SOURCE_STATUSES,
                )
            ]
            latest_barangay_by_id = {
                int(row["barangay_id"]): row
                for row in latest_barangay_rows
            }

            allocations_by_center: dict[
                int,
                list[dict[str, object]],
            ] = defaultdict(list)

            for allocation in allocation_rows:
                if (
                    int(allocation["families"]) <= 0
                    and int(allocation["individuals"]) <= 0
                ):
                    continue

                allocations_by_center[
                    int(allocation["evacuation_center_id"])
                ].append(allocation)

            attributed_families: dict[int, int] = defaultdict(int)
            attributed_individuals: dict[int, int] = defaultdict(int)
            attributed_center_ids: dict[int, set[int]] = defaultdict(set)
            relevant_times: dict[int, list[datetime]] = defaultdict(list)
            source_present: set[int] = set()
            allocation_conflict_barangays: set[int] = set()

            for ec_row in latest_ec_rows:
                if ec_row["status"] not in ACTIVE_CENTER_STATUSES:
                    continue

                center_id = int(
                    ec_row["evacuation_center_id"]
                )
                host_barangay_id = int(
                    ec_row["barangay_id"]
                )
                center_families = int(
                    ec_row["families"]
                )
                center_individuals = int(
                    ec_row["individuals"]
                )

                center_allocations = (
                    allocations_by_center.get(
                        center_id,
                        [],
                    )
                )

                foreign_families = sum(
                    int(row["families"])
                    for row in center_allocations
                )
                foreign_individuals = sum(
                    int(row["individuals"])
                    for row in center_allocations
                )

                conflict = (
                    foreign_families > center_families
                    or foreign_individuals > center_individuals
                )

                if conflict:
                    allocation_conflict_barangays.add(
                        host_barangay_id
                    )
                    for allocation in center_allocations:
                        allocation_conflict_barangays.add(
                            int(
                                allocation[
                                    "origin_barangay_id"
                                ]
                            )
                        )

                host_families = max(
                    0,
                    center_families - foreign_families,
                )
                host_individuals = max(
                    0,
                    center_individuals - foreign_individuals,
                )

                attributed_families[
                    host_barangay_id
                ] += host_families
                attributed_individuals[
                    host_barangay_id
                ] += host_individuals
                attributed_center_ids[
                    host_barangay_id
                ].add(center_id)
                source_present.add(
                    host_barangay_id
                )

                if ec_row["recorded_at"] is not None:
                    relevant_times[
                        host_barangay_id
                    ].append(
                        ec_row["recorded_at"]
                    )

                for allocation in center_allocations:
                    origin_id = int(
                        allocation[
                            "origin_barangay_id"
                        ]
                    )
                    attributed_families[
                        origin_id
                    ] += int(
                        allocation["families"]
                    )
                    attributed_individuals[
                        origin_id
                    ] += int(
                        allocation["individuals"]
                    )
                    attributed_center_ids[
                        origin_id
                    ].add(center_id)
                    source_present.add(origin_id)

                    if (
                        allocation["recorded_at"]
                        is not None
                    ):
                        relevant_times[
                            origin_id
                        ].append(
                            allocation[
                                "recorded_at"
                            ]
                        )

            results: list[dict[str, object]] = []

            for barangay in barangays:
                barangay_id = int(
                    barangay["id"]
                )

                report = latest_barangay_by_id.get(
                    barangay_id
                )

                ec_families = attributed_families[
                    barangay_id
                ]
                ec_individuals = attributed_individuals[
                    barangay_id
                ]
                latest_ec_at = (
                    max(
                        relevant_times[
                            barangay_id
                        ]
                    )
                    if relevant_times[
                        barangay_id
                    ]
                    else None
                )

                if report is None:
                    reconciliation_status = (
                        "No Barangay Report"
                        if barangay_id in source_present
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
                        report["inside_ec_families"]
                    )
                    barangay_individuals = int(
                        report["inside_ec_individuals"]
                    )
                    barangay_status = (
                        report["validation_status"]
                    )
                    barangay_recorded_at = (
                        report["recorded_at"]
                    )
                    family_difference = (
                        barangay_families
                        - ec_families
                    )
                    individual_difference = (
                        barangay_individuals
                        - ec_individuals
                    )

                    if (
                        barangay_id
                        in allocation_conflict_barangays
                    ):
                        reconciliation_status = (
                            "Allocation Conflict"
                        )
                    elif barangay_id not in source_present:
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
                        "barangay_inside_families": (
                            barangay_families
                        ),
                        "barangay_inside_individuals": (
                            barangay_individuals
                        ),
                        "barangay_validation_status": (
                            barangay_status
                        ),
                        "barangay_recorded_at": (
                            barangay_recorded_at
                        ),
                        "ec_inside_families": (
                            ec_families
                        ),
                        "ec_inside_individuals": (
                            ec_individuals
                        ),
                        "ec_operational_centers": len(
                            attributed_center_ids[
                                barangay_id
                            ]
                        ),
                        "latest_ec_recorded_at": (
                            latest_ec_at
                        ),
                        "family_difference": (
                            family_difference
                        ),
                        "individual_difference": (
                            individual_difference
                        ),
                        "reconciliation_status": (
                            reconciliation_status
                        ),
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

        if (
            report.validation_status
            not in PENDING_REVIEW_STATUSES
        ):
            raise ReportAlreadyReviewedError(
                "This barangay report has already been reviewed."
            )

        report.validation_status = decision
        report.reviewed_by_user_id = reviewer.id
        report.reviewed_by = (
            _reviewer_snapshot(reviewer)
        )
        report.review_notes = cleaned_notes
        report.reviewed_at = datetime.now(
            MANILA_TIMEZONE
        )
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

        if (
            report.validation_status
            not in PENDING_REVIEW_STATUSES
        ):
            raise ReportAlreadyReviewedError(
                "This evacuation-center report has already been reviewed."
            )

        report.validation_status = decision
        report.reviewed_by_user_id = reviewer.id
        report.reviewed_by = (
            _reviewer_snapshot(reviewer)
        )
        report.review_notes = cleaned_notes
        report.reviewed_at = datetime.now(
            MANILA_TIMEZONE
        )
        session.flush()
