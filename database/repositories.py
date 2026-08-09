from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import (
    AlertLevel,
    Barangay,
    BarangayUpdate,
    DisasterEvent,
    EvacuationCenter,
    EvacuationCenterUpdate,
    EventChangeHistory,
    Incident,
    IncidentHistory,
    ResponseResource,
    IncidentResourceAssignment,
    CrossBarangayEvacuationAllocation,
    ReportSnapshot,
    AppUser,
)
def fetch_active_event_rows(session: Session):
    """
    Return all disaster events currently marked active.

    Normally, this should return zero or one row.
    Returning more than one indicates a data-integrity problem.
    """
    statement = (
        select(
            DisasterEvent.id,
            DisasterEvent.event_name,
            DisasterEvent.hazard_type,
            DisasterEvent.classification,
            DisasterEvent.eoc_status,
            DisasterEvent.current_sitrep_number,
            DisasterEvent.official_reference,
            DisasterEvent.situation_overview,
            DisasterEvent.started_at,
            DisasterEvent.ended_at,
            DisasterEvent.is_active,
            DisasterEvent.created_at,
            DisasterEvent.updated_at,
            AlertLevel.id.label("alert_level_id"),
            AlertLevel.code.label("alert_code"),
            AlertLevel.name.label("alert_name"),
            AlertLevel.color_hex.label("alert_color"),
        )
        .join(
            AlertLevel,
            AlertLevel.id == DisasterEvent.current_alert_level_id,
        )
        .where(
            DisasterEvent.is_active.is_(True)
        )
        .order_by(
            DisasterEvent.started_at.desc()
        )
    )

    return session.execute(statement).mappings().all()


def fetch_alert_levels(session: Session):
    """
    Return active alert levels in their configured display order.
    """
    statement = (
        select(
            AlertLevel.id,
            AlertLevel.code,
            AlertLevel.name,
            AlertLevel.description,
            AlertLevel.color_hex,
            AlertLevel.display_order,
        )
        .where(
            AlertLevel.is_active.is_(True)
        )
        .order_by(
            AlertLevel.display_order
        )
    )

    return session.execute(statement).mappings().all()


def fetch_alert_level_by_code(
    session: Session,
    alert_code: str,
) -> AlertLevel | None:
    """
    Retrieve one alert-level model using its code.
    """
    statement = select(AlertLevel).where(
        AlertLevel.code == alert_code
    )

    return session.scalar(statement)


def fetch_active_barangays(session: Session):
    """
    Return all active Naic barangays alphabetically.
    """
    statement = (
        select(
            Barangay.id,
            Barangay.psgc_code,
            Barangay.name,
        )
        .where(
            Barangay.is_active.is_(True)
        )
        .order_by(
            Barangay.name.asc()
        )
    )

    return session.execute(statement).mappings().all()


def fetch_barangay_by_id(
    session: Session,
    barangay_id: int,
) -> Barangay | None:
    """
    Retrieve one active barangay using its database ID.
    """
    statement = select(Barangay).where(
        Barangay.id == barangay_id,
        Barangay.is_active.is_(True),
    )

    return session.scalar(statement)


def fetch_recent_barangay_updates(
    session: Session,
    *,
    event_id: int,
    limit: int = 20,
):
    """
    Return the newest barangay updates for one event.
    """
    statement = (
        select(
            BarangayUpdate.id,
            BarangayUpdate.event_id,
            BarangayUpdate.barangay_id,
            Barangay.name.label("barangay_name"),
            BarangayUpdate.situation_status,
            BarangayUpdate.affected_families,
            BarangayUpdate.affected_individuals,
            BarangayUpdate.inside_ec_families,
            BarangayUpdate.inside_ec_individuals,
            BarangayUpdate.outside_ec_families,
            BarangayUpdate.outside_ec_individuals,
            BarangayUpdate.flood_status,
            BarangayUpdate.flood_depth_cm,
            BarangayUpdate.road_status,
            BarangayUpdate.power_status,
            BarangayUpdate.water_status,
            BarangayUpdate.rescue_requests,
            BarangayUpdate.source,
            BarangayUpdate.validation_status,
            BarangayUpdate.remarks,
            BarangayUpdate.recorded_at,
        )
        .join(
            Barangay,
            Barangay.id == BarangayUpdate.barangay_id,
        )
        .where(
            BarangayUpdate.event_id == event_id
        )
        .order_by(
            BarangayUpdate.recorded_at.desc(),
            BarangayUpdate.id.desc(),
        )
        .limit(limit)
    )

    return session.execute(statement).mappings().all()


def fetch_latest_barangay_updates_for_event(
    session: Session,
    *,
    event_id: int,
    included_statuses: tuple[str, ...] | None = None,
):
    """
    Retrieve the latest barangay update for every barangay
    under one disaster event.

    When included_statuses is provided, only records with
    those validation statuses are considered before selecting
    the latest record.
    """

    filters = [
        BarangayUpdate.event_id == event_id,
    ]

    if included_statuses is not None:
        filters.append(
            BarangayUpdate.validation_status.in_(
                included_statuses
            )
        )

    ranked_updates = (
        select(
            BarangayUpdate.id.label("id"),
            BarangayUpdate.event_id.label("event_id"),
            BarangayUpdate.barangay_id.label("barangay_id"),
            Barangay.name.label("barangay_name"),
            Barangay.psgc_code.label("psgc_code"),
            BarangayUpdate.situation_status.label(
                "situation_status"
            ),
            BarangayUpdate.affected_families.label(
                "affected_families"
            ),
            BarangayUpdate.affected_individuals.label(
                "affected_individuals"
            ),
            BarangayUpdate.inside_ec_families.label(
                "inside_ec_families"
            ),
            BarangayUpdate.inside_ec_individuals.label(
                "inside_ec_individuals"
            ),
            BarangayUpdate.outside_ec_families.label(
                "outside_ec_families"
            ),
            BarangayUpdate.outside_ec_individuals.label(
                "outside_ec_individuals"
            ),
            BarangayUpdate.flood_status.label(
                "flood_status"
            ),
            BarangayUpdate.flood_depth_cm.label(
                "flood_depth_cm"
            ),
            BarangayUpdate.road_status.label(
                "road_status"
            ),
            BarangayUpdate.power_status.label(
                "power_status"
            ),
            BarangayUpdate.water_status.label(
                "water_status"
            ),
            BarangayUpdate.rescue_requests.label(
                "rescue_requests"
            ),
            BarangayUpdate.source.label("source"),
            BarangayUpdate.validation_status.label(
                "validation_status"
            ),
            BarangayUpdate.remarks.label("remarks"),
            BarangayUpdate.recorded_at.label(
                "recorded_at"
            ),
            func.row_number()
            .over(
                partition_by=BarangayUpdate.barangay_id,
                order_by=(
                    BarangayUpdate.recorded_at.desc(),
                    BarangayUpdate.id.desc(),
                ),
            )
            .label("row_rank"),
        )
        .join(
            Barangay,
            Barangay.id == BarangayUpdate.barangay_id,
        )
        .where(*filters)
        .subquery()
    )

    statement = (
        select(
            ranked_updates.c.id,
            ranked_updates.c.event_id,
            ranked_updates.c.barangay_id,
            ranked_updates.c.barangay_name,
            ranked_updates.c.psgc_code,
            ranked_updates.c.situation_status,
            ranked_updates.c.affected_families,
            ranked_updates.c.affected_individuals,
            ranked_updates.c.inside_ec_families,
            ranked_updates.c.inside_ec_individuals,
            ranked_updates.c.outside_ec_families,
            ranked_updates.c.outside_ec_individuals,
            ranked_updates.c.flood_status,
            ranked_updates.c.flood_depth_cm,
            ranked_updates.c.road_status,
            ranked_updates.c.power_status,
            ranked_updates.c.water_status,
            ranked_updates.c.rescue_requests,
            ranked_updates.c.source,
            ranked_updates.c.validation_status,
            ranked_updates.c.remarks,
            ranked_updates.c.recorded_at,
        )
        .where(
            ranked_updates.c.row_rank == 1
        )
        .order_by(
            ranked_updates.c.barangay_name.asc()
        )
    )

    return session.execute(statement).mappings().all()


def fetch_barangay_validation_queue(
    session: Session,
    *,
    event_id: int,
):
    """
    Retrieve reports awaiting validation for one event.
    """
    statement = (
        select(
            BarangayUpdate.id,
            BarangayUpdate.event_id,
            BarangayUpdate.barangay_id,
            Barangay.name.label("barangay_name"),
            Barangay.psgc_code.label("psgc_code"),
            BarangayUpdate.situation_status,
            BarangayUpdate.affected_families,
            BarangayUpdate.affected_individuals,
            BarangayUpdate.inside_ec_families,
            BarangayUpdate.inside_ec_individuals,
            BarangayUpdate.outside_ec_families,
            BarangayUpdate.outside_ec_individuals,
            BarangayUpdate.flood_status,
            BarangayUpdate.flood_depth_cm,
            BarangayUpdate.road_status,
            BarangayUpdate.power_status,
            BarangayUpdate.water_status,
            BarangayUpdate.rescue_requests,
            BarangayUpdate.source,
            BarangayUpdate.validation_status,
            BarangayUpdate.remarks,
            BarangayUpdate.recorded_at,
        )
        .join(
            Barangay,
            Barangay.id == BarangayUpdate.barangay_id,
        )
        .where(
            BarangayUpdate.event_id == event_id,
            BarangayUpdate.validation_status.in_(
                (
                    "Submitted",
                    "For Validation",
                )
            ),
        )
        .order_by(
            BarangayUpdate.recorded_at.desc(),
            BarangayUpdate.id.desc(),
        )
    )

    return session.execute(statement).mappings().all()


def fetch_barangay_update_for_review(
    session: Session,
    *,
    update_id: int,
) -> BarangayUpdate | None:
    """
    Retrieve and lock one barangay update while it is
    being reviewed.
    """
    statement = (
        select(BarangayUpdate)
        .where(
            BarangayUpdate.id == update_id
        )
        .with_for_update()
    )

    return session.scalar(statement)


def fetch_active_evacuation_centers(
    session: Session,
):
    """
    Return all active evacuation centers with their
    associated barangays.
    """
    statement = (
        select(
            EvacuationCenter.id,
            EvacuationCenter.name,
            EvacuationCenter.barangay_id,
            Barangay.name.label("barangay_name"),
            Barangay.psgc_code.label("psgc_code"),
            EvacuationCenter.address,
            EvacuationCenter.safe_capacity,
            EvacuationCenter.is_active,
            EvacuationCenter.created_at,
            EvacuationCenter.updated_at,
        )
        .join(
            Barangay,
            Barangay.id == EvacuationCenter.barangay_id,
        )
        .where(
            EvacuationCenter.is_active.is_(True)
        )
        .order_by(
            EvacuationCenter.name.asc()
        )
    )

    return session.execute(statement).mappings().all()


def fetch_evacuation_center_by_id(
    session: Session,
    *,
    center_id: int,
) -> EvacuationCenter | None:
    """
    Retrieve one active evacuation center by ID.
    """
    statement = select(EvacuationCenter).where(
        EvacuationCenter.id == center_id,
        EvacuationCenter.is_active.is_(True),
    )

    return session.scalar(statement)


def fetch_evacuation_center_by_name_barangay(
    session: Session,
    *,
    name: str,
    barangay_id: int,
) -> EvacuationCenter | None:
    """
    Check for a duplicate center name in one barangay.
    """
    statement = select(EvacuationCenter).where(
        func.lower(EvacuationCenter.name)
        == name.strip().lower(),
        EvacuationCenter.barangay_id == barangay_id,
    )

    return session.scalar(statement)


def fetch_recent_evacuation_center_updates(
    session: Session,
    *,
    event_id: int,
    limit: int = 20,
):
    """
    Retrieve recent evacuation-center reports for one event.
    """
    statement = (
        select(
            EvacuationCenterUpdate.id,
            EvacuationCenterUpdate.event_id,
            EvacuationCenterUpdate.evacuation_center_id,
            EvacuationCenter.name.label("center_name"),
            Barangay.name.label("barangay_name"),
            EvacuationCenter.safe_capacity,
            EvacuationCenterUpdate.status,
            EvacuationCenterUpdate.families,
            EvacuationCenterUpdate.individuals,
            EvacuationCenterUpdate.children,
            EvacuationCenterUpdate.senior_citizens,
            EvacuationCenterUpdate.pwd,
            EvacuationCenterUpdate.pregnant_women,
            EvacuationCenterUpdate.medical_cases,
            EvacuationCenterUpdate.food_status,
            EvacuationCenterUpdate.water_status,
            EvacuationCenterUpdate.electricity_status,
            EvacuationCenterUpdate.sanitation_status,
            EvacuationCenterUpdate.source,
            EvacuationCenterUpdate.validation_status,
            EvacuationCenterUpdate.remarks,
            EvacuationCenterUpdate.recorded_at,
        )
        .join(
            EvacuationCenter,
            EvacuationCenter.id
            == EvacuationCenterUpdate.evacuation_center_id,
        )
        .join(
            Barangay,
            Barangay.id == EvacuationCenter.barangay_id,
        )
        .where(
            EvacuationCenterUpdate.event_id == event_id
        )
        .order_by(
            EvacuationCenterUpdate.recorded_at.desc(),
            EvacuationCenterUpdate.id.desc(),
        )
        .limit(limit)
    )

    return session.execute(statement).mappings().all()


def fetch_latest_evacuation_updates_for_event(
    session: Session,
    *,
    event_id: int,
    included_statuses: tuple[str, ...] | None = None,
):
    """
    Return the latest evacuation-center update for every
    center under one disaster event.
    """
    filters = [
        EvacuationCenterUpdate.event_id == event_id,
    ]

    if included_statuses is not None:
        filters.append(
            EvacuationCenterUpdate.validation_status.in_(
                included_statuses
            )
        )

    ranked_updates = (
        select(
            EvacuationCenterUpdate.id.label("id"),
            EvacuationCenterUpdate.event_id.label(
                "event_id"
            ),
            EvacuationCenterUpdate.evacuation_center_id.label(
                "evacuation_center_id"
            ),
            EvacuationCenter.name.label("center_name"),
            Barangay.name.label("barangay_name"),
            EvacuationCenter.safe_capacity.label(
                "safe_capacity"
            ),
            EvacuationCenterUpdate.status.label("status"),
            EvacuationCenterUpdate.families.label(
                "families"
            ),
            EvacuationCenterUpdate.individuals.label(
                "individuals"
            ),
            EvacuationCenterUpdate.children.label(
                "children"
            ),
            EvacuationCenterUpdate.senior_citizens.label(
                "senior_citizens"
            ),
            EvacuationCenterUpdate.pwd.label("pwd"),
            EvacuationCenterUpdate.pregnant_women.label(
                "pregnant_women"
            ),
            EvacuationCenterUpdate.medical_cases.label(
                "medical_cases"
            ),
            EvacuationCenterUpdate.food_status.label(
                "food_status"
            ),
            EvacuationCenterUpdate.water_status.label(
                "water_status"
            ),
            EvacuationCenterUpdate.electricity_status.label(
                "electricity_status"
            ),
            EvacuationCenterUpdate.sanitation_status.label(
                "sanitation_status"
            ),
            EvacuationCenterUpdate.source.label("source"),
            EvacuationCenterUpdate.validation_status.label(
                "validation_status"
            ),
            EvacuationCenterUpdate.remarks.label("remarks"),
            EvacuationCenterUpdate.recorded_at.label(
                "recorded_at"
            ),
            func.row_number()
            .over(
                partition_by=(
                    EvacuationCenterUpdate.evacuation_center_id
                ),
                order_by=(
                    EvacuationCenterUpdate.recorded_at.desc(),
                    EvacuationCenterUpdate.id.desc(),
                ),
            )
            .label("row_rank"),
        )
        .join(
            EvacuationCenter,
            EvacuationCenter.id
            == EvacuationCenterUpdate.evacuation_center_id,
        )
        .join(
            Barangay,
            Barangay.id == EvacuationCenter.barangay_id,
        )
        .where(*filters)
        .subquery()
    )

    statement = (
        select(
            ranked_updates.c.id,
            ranked_updates.c.event_id,
            ranked_updates.c.evacuation_center_id,
            ranked_updates.c.center_name,
            ranked_updates.c.barangay_name,
            ranked_updates.c.safe_capacity,
            ranked_updates.c.status,
            ranked_updates.c.families,
            ranked_updates.c.individuals,
            ranked_updates.c.children,
            ranked_updates.c.senior_citizens,
            ranked_updates.c.pwd,
            ranked_updates.c.pregnant_women,
            ranked_updates.c.medical_cases,
            ranked_updates.c.food_status,
            ranked_updates.c.water_status,
            ranked_updates.c.electricity_status,
            ranked_updates.c.sanitation_status,
            ranked_updates.c.source,
            ranked_updates.c.validation_status,
            ranked_updates.c.remarks,
            ranked_updates.c.recorded_at,
        )
        .where(
            ranked_updates.c.row_rank == 1
        )
        .order_by(
            ranked_updates.c.center_name.asc()
        )
    )

    return session.execute(statement).mappings().all()


def fetch_app_user_by_email(
    session: Session,
    *,
    email: str,
) -> AppUser | None:
    """
    Retrieve an application user by normalized email.
    """
    normalized_email = email.strip().lower()

    statement = select(AppUser).where(
        func.lower(AppUser.email)
        == normalized_email
    )

    return session.scalar(statement)


def fetch_app_user_by_id(
    session: Session,
    *,
    user_id: int,
) -> AppUser | None:
    """
    Retrieve an application user by database ID.
    """
    statement = select(AppUser).where(
        AppUser.id == user_id
    )

    return session.scalar(statement)


def fetch_all_app_users(
    session: Session,
):
    """
    Retrieve all application users.
    """
    statement = (
        select(AppUser)
        .order_by(
            AppUser.is_active.desc(),
            AppUser.display_name.asc(),
            AppUser.email.asc(),
        )
    )

    return session.scalars(statement).all()

def fetch_event_by_id(
    session: Session,
    *,
    event_id: int,
    for_update: bool = False,
) -> DisasterEvent | None:
    statement = select(
        DisasterEvent
    ).where(
        DisasterEvent.id == event_id
    )

    if for_update:
        statement = (
            statement.with_for_update()
        )

    return session.scalar(
        statement
    )


def fetch_recent_events(
    session: Session,
    *,
    limit: int = 20,
):
    statement = (
        select(
            DisasterEvent.id,
            DisasterEvent.event_name,
            DisasterEvent.hazard_type,
            DisasterEvent.classification,
            DisasterEvent.eoc_status,
            DisasterEvent.current_sitrep_number,
            DisasterEvent.official_reference,
            DisasterEvent.situation_overview,
            DisasterEvent.started_at,
            DisasterEvent.ended_at,
            DisasterEvent.is_active,
            AlertLevel.code.label(
                "alert_code"
            ),
            AlertLevel.name.label(
                "alert_name"
            ),
        )
        .join(
            AlertLevel,
            AlertLevel.id
            == DisasterEvent.current_alert_level_id,
        )
        .order_by(
            DisasterEvent.started_at.desc(),
            DisasterEvent.id.desc(),
        )
        .limit(limit)
    )

    return session.execute(
        statement
    ).mappings().all()


def fetch_event_change_history(
    session: Session,
    *,
    event_id: int,
    limit: int = 100,
):
    statement = (
        select(
            EventChangeHistory.id,
            EventChangeHistory.event_id,
            EventChangeHistory.change_type,
            EventChangeHistory.field_name,
            EventChangeHistory.previous_value,
            EventChangeHistory.new_value,
            EventChangeHistory.reason,
            EventChangeHistory.authority_reference,
            EventChangeHistory.changed_by_user_id,
            EventChangeHistory.changed_by,
            EventChangeHistory.effective_at,
            EventChangeHistory.created_at,
        )
        .where(
            EventChangeHistory.event_id
            == event_id
        )
        .order_by(
            EventChangeHistory.effective_at.desc(),
            EventChangeHistory.id.desc(),
        )
        .limit(limit)
    )

    return session.execute(
        statement
    ).mappings().all()


def fetch_barangay_update_by_submission_key(
    session: Session,
    *,
    submission_key: str,
) -> BarangayUpdate | None:
    return session.scalar(
        select(
            BarangayUpdate
        ).where(
            BarangayUpdate.submission_key
            == submission_key
        )
    )


def fetch_evacuation_update_by_submission_key(
    session: Session,
    *,
    submission_key: str,
) -> EvacuationCenterUpdate | None:
    return session.scalar(
        select(
            EvacuationCenterUpdate
        ).where(
            EvacuationCenterUpdate.submission_key
            == submission_key
        )
    )


def fetch_latest_barangay_update_for_barangay(
    session: Session,
    *,
    event_id: int,
    barangay_id: int,
    included_statuses: tuple[str, ...] | None = None,
) -> BarangayUpdate | None:
    filters = [
        BarangayUpdate.event_id
        == event_id,
        BarangayUpdate.barangay_id
        == barangay_id,
    ]

    if included_statuses is not None:
        filters.append(
            BarangayUpdate.validation_status.in_(
                included_statuses
            )
        )

    statement = (
        select(
            BarangayUpdate
        )
        .where(
            *filters
        )
        .order_by(
            BarangayUpdate.recorded_at.desc(),
            BarangayUpdate.id.desc(),
        )
        .limit(1)
    )

    return session.scalar(
        statement
    )


def fetch_latest_evacuation_updates_for_barangay(
    session: Session,
    *,
    event_id: int,
    barangay_id: int,
    included_statuses: tuple[str, ...] | None = None,
):
    filters = [
        EvacuationCenterUpdate.event_id
        == event_id,
        EvacuationCenter.barangay_id
        == barangay_id,
    ]

    if included_statuses is not None:
        filters.append(
            EvacuationCenterUpdate.validation_status.in_(
                included_statuses
            )
        )

    ranked_updates = (
        select(
            EvacuationCenterUpdate.id.label(
                "id"
            ),
            EvacuationCenterUpdate.evacuation_center_id.label(
                "evacuation_center_id"
            ),
            EvacuationCenterUpdate.status.label(
                "status"
            ),
            EvacuationCenterUpdate.families.label(
                "families"
            ),
            EvacuationCenterUpdate.individuals.label(
                "individuals"
            ),
            EvacuationCenterUpdate.recorded_at.label(
                "recorded_at"
            ),
            func.row_number()
            .over(
                partition_by=(
                    EvacuationCenterUpdate.evacuation_center_id
                ),
                order_by=(
                    EvacuationCenterUpdate.recorded_at.desc(),
                    EvacuationCenterUpdate.id.desc(),
                ),
            )
            .label(
                "row_rank"
            ),
        )
        .join(
            EvacuationCenter,
            EvacuationCenter.id
            == EvacuationCenterUpdate.evacuation_center_id,
        )
        .where(
            *filters
        )
        .subquery()
    )

    statement = (
        select(
            ranked_updates.c.id,
            ranked_updates.c.evacuation_center_id,
            ranked_updates.c.status,
            ranked_updates.c.families,
            ranked_updates.c.individuals,
            ranked_updates.c.recorded_at,
        )
        .where(
            ranked_updates.c.row_rank
            == 1
        )
    )

    return session.execute(
        statement
    ).mappings().all()

def fetch_evacuation_validation_queue(
    session: Session,
    *,
    event_id: int,
):
    statement = (
        select(
            EvacuationCenterUpdate.id,
            EvacuationCenterUpdate.event_id,
            EvacuationCenterUpdate.evacuation_center_id,
            EvacuationCenter.name.label("center_name"),
            EvacuationCenter.barangay_id.label("barangay_id"),
            Barangay.name.label("barangay_name"),
            EvacuationCenter.safe_capacity,
            EvacuationCenterUpdate.status,
            EvacuationCenterUpdate.families,
            EvacuationCenterUpdate.individuals,
            EvacuationCenterUpdate.children,
            EvacuationCenterUpdate.senior_citizens,
            EvacuationCenterUpdate.pwd,
            EvacuationCenterUpdate.pregnant_women,
            EvacuationCenterUpdate.medical_cases,
            EvacuationCenterUpdate.food_status,
            EvacuationCenterUpdate.water_status,
            EvacuationCenterUpdate.electricity_status,
            EvacuationCenterUpdate.sanitation_status,
            EvacuationCenterUpdate.source,
            EvacuationCenterUpdate.validation_status,
            EvacuationCenterUpdate.remarks,
            EvacuationCenterUpdate.recorded_at,
        )
        .join(
            EvacuationCenter,
            EvacuationCenter.id
            == EvacuationCenterUpdate.evacuation_center_id,
        )
        .join(
            Barangay,
            Barangay.id == EvacuationCenter.barangay_id,
        )
        .where(
            EvacuationCenterUpdate.event_id == event_id,
            EvacuationCenterUpdate.validation_status.in_(
                (
                    "Submitted",
                    "For Validation",
                )
            ),
        )
        .order_by(
            EvacuationCenterUpdate.recorded_at.desc(),
            EvacuationCenterUpdate.id.desc(),
        )
    )

    return session.execute(statement).mappings().all()


def fetch_evacuation_update_for_review(
    session: Session,
    *,
    update_id: int,
) -> EvacuationCenterUpdate | None:
    statement = (
        select(EvacuationCenterUpdate)
        .where(
            EvacuationCenterUpdate.id == update_id
        )
        .with_for_update()
    )

    return session.scalar(statement)


def fetch_needs_correction_barangay_updates(
    session: Session,
    *,
    event_id: int,
    barangay_id: int,
):
    statement = (
        select(BarangayUpdate)
        .where(
            BarangayUpdate.event_id == event_id,
            BarangayUpdate.barangay_id == barangay_id,
            BarangayUpdate.validation_status == "Needs Correction",
        )
        .order_by(
            BarangayUpdate.recorded_at.desc(),
            BarangayUpdate.id.desc(),
        )
        .with_for_update()
    )

    return session.scalars(statement).all()


def fetch_needs_correction_evacuation_updates(
    session: Session,
    *,
    event_id: int,
    center_id: int,
):
    statement = (
        select(EvacuationCenterUpdate)
        .where(
            EvacuationCenterUpdate.event_id == event_id,
            EvacuationCenterUpdate.evacuation_center_id == center_id,
            EvacuationCenterUpdate.validation_status == "Needs Correction",
        )
        .order_by(
            EvacuationCenterUpdate.recorded_at.desc(),
            EvacuationCenterUpdate.id.desc(),
        )
        .with_for_update()
    )

    return session.scalars(statement).all()

def fetch_incident_by_submission_key(
    session: Session,
    *,
    submission_key: str,
) -> Incident | None:
    return session.scalar(
        select(Incident).where(
            Incident.submission_key == submission_key
        )
    )


def fetch_incident_by_id(
    session: Session,
    *,
    incident_id: int,
    for_update: bool = False,
) -> Incident | None:
    statement = select(Incident).where(
        Incident.id == incident_id
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def fetch_recent_incidents(
    session: Session,
    *,
    event_id: int,
    limit: int = 100,
):
    statement = (
        select(
            Incident.id,
            Incident.event_id,
            Incident.control_number,
            Incident.barangay_id,
            Barangay.name.label("barangay_name"),
            Incident.exact_location,
            Incident.incident_type,
            Incident.description,
            Incident.priority,
            Incident.persons_affected,
            Incident.status,
            Incident.assigned_team,
            Incident.assigned_vehicle,
            Incident.action_taken,
            Incident.source,
            Incident.validation_status,
            Incident.reported_by,
            Incident.reported_at,
            Incident.updated_at,
            Incident.resolved_at,
        )
        .join(Barangay, Barangay.id == Incident.barangay_id)
        .where(Incident.event_id == event_id)
        .order_by(
            Incident.reported_at.desc(),
            Incident.id.desc(),
        )
        .limit(limit)
    )
    return session.execute(statement).mappings().all()


def fetch_incident_history(
    session: Session,
    *,
    incident_id: int,
    limit: int = 100,
):
    statement = (
        select(
            IncidentHistory.id,
            IncidentHistory.incident_id,
            IncidentHistory.change_type,
            IncidentHistory.field_name,
            IncidentHistory.previous_value,
            IncidentHistory.new_value,
            IncidentHistory.notes,
            IncidentHistory.changed_by,
            IncidentHistory.effective_at,
            IncidentHistory.created_at,
        )
        .where(IncidentHistory.incident_id == incident_id)
        .order_by(
            IncidentHistory.effective_at.desc(),
            IncidentHistory.id.desc(),
        )
        .limit(limit)
    )
    return session.execute(statement).mappings().all()


def fetch_response_resources(session: Session):
    statement = (
        select(
            ResponseResource.id,
            ResponseResource.resource_code,
            ResponseResource.name,
            ResponseResource.resource_type,
            ResponseResource.subtype,
            ResponseResource.details,
            ResponseResource.status,
            ResponseResource.is_active,
            ResponseResource.created_at,
            ResponseResource.updated_at,
        )
        .order_by(
            ResponseResource.resource_type,
            ResponseResource.resource_code,
        )
    )
    return session.execute(statement).mappings().all()


def fetch_resource_by_code(
    session: Session,
    *,
    resource_code: str,
) -> ResponseResource | None:
    return session.scalar(
        select(ResponseResource).where(
            ResponseResource.resource_code == resource_code
        )
    )


def fetch_resource_by_id(
    session: Session,
    *,
    resource_id: int,
    for_update: bool = False,
) -> ResponseResource | None:
    statement = select(ResponseResource).where(
        ResponseResource.id == resource_id
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def fetch_active_resource_assignment(
    session: Session,
    *,
    resource_id: int,
    for_update: bool = False,
) -> IncidentResourceAssignment | None:
    statement = select(
        IncidentResourceAssignment
    ).where(
        IncidentResourceAssignment.resource_id == resource_id,
        IncidentResourceAssignment.released_at.is_(None),
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def fetch_assignment_by_id(
    session: Session,
    *,
    assignment_id: int,
    for_update: bool = False,
) -> IncidentResourceAssignment | None:
    statement = select(
        IncidentResourceAssignment
    ).where(
        IncidentResourceAssignment.id == assignment_id
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def fetch_incident_active_assignments(
    session: Session,
    *,
    incident_id: int,
    for_update: bool = False,
):
    statement = (
        select(
            IncidentResourceAssignment,
            ResponseResource,
        )
        .join(
            ResponseResource,
            ResponseResource.id
            == IncidentResourceAssignment.resource_id,
        )
        .where(
            IncidentResourceAssignment.incident_id == incident_id,
            IncidentResourceAssignment.released_at.is_(None),
        )
        .order_by(IncidentResourceAssignment.assigned_at)
    )
    if for_update:
        statement = statement.with_for_update()
    return session.execute(statement).all()


def fetch_latest_evacuation_update_for_center(
    session: Session,
    *,
    event_id: int,
    center_id: int,
    included_statuses: tuple[str, ...] | None = None,
):
    filters = [
        EvacuationCenterUpdate.event_id == event_id,
        EvacuationCenterUpdate.evacuation_center_id == center_id,
    ]
    if included_statuses is not None:
        filters.append(
            EvacuationCenterUpdate.validation_status.in_(
                included_statuses
            )
        )
    statement = (
        select(
            EvacuationCenterUpdate.id,
            EvacuationCenterUpdate.evacuation_center_id,
            EvacuationCenterUpdate.status,
            EvacuationCenterUpdate.families,
            EvacuationCenterUpdate.individuals,
            EvacuationCenterUpdate.validation_status,
            EvacuationCenterUpdate.recorded_at,
        )
        .where(*filters)
        .order_by(
            EvacuationCenterUpdate.recorded_at.desc(),
            EvacuationCenterUpdate.id.desc(),
        )
        .limit(1)
    )
    return session.execute(statement).mappings().first()


def fetch_latest_evacuation_updates_for_event(
    session: Session,
    *,
    event_id: int,
    included_statuses: tuple[str, ...] | None = None,
):
    """
    Return the latest report for every active evacuation center.

    This result shape is shared by the dashboard, validation, and
    reconciliation services. Keep all operational fields here.
    """
    filters = [
        EvacuationCenterUpdate.event_id == event_id,
        EvacuationCenter.is_active.is_(True),
    ]

    if included_statuses is not None:
        filters.append(
            EvacuationCenterUpdate.validation_status.in_(
                included_statuses
            )
        )

    ranked = (
        select(
            EvacuationCenterUpdate.id.label("id"),
            EvacuationCenterUpdate.evacuation_center_id.label(
                "evacuation_center_id"
            ),
            EvacuationCenter.barangay_id.label(
                "barangay_id"
            ),
            EvacuationCenter.name.label(
                "center_name"
            ),
            EvacuationCenter.safe_capacity.label(
                "safe_capacity"
            ),
            EvacuationCenterUpdate.status.label(
                "status"
            ),
            EvacuationCenterUpdate.families.label(
                "families"
            ),
            EvacuationCenterUpdate.individuals.label(
                "individuals"
            ),
            EvacuationCenterUpdate.children.label(
                "children"
            ),
            EvacuationCenterUpdate.senior_citizens.label(
                "senior_citizens"
            ),
            EvacuationCenterUpdate.pwd.label(
                "pwd"
            ),
            EvacuationCenterUpdate.pregnant_women.label(
                "pregnant_women"
            ),
            EvacuationCenterUpdate.medical_cases.label(
                "medical_cases"
            ),
            EvacuationCenterUpdate.food_status.label(
                "food_status"
            ),
            EvacuationCenterUpdate.water_status.label(
                "water_status"
            ),
            EvacuationCenterUpdate.electricity_status.label(
                "electricity_status"
            ),
            EvacuationCenterUpdate.sanitation_status.label(
                "sanitation_status"
            ),
            EvacuationCenterUpdate.source.label(
                "source"
            ),
            EvacuationCenterUpdate.validation_status.label(
                "validation_status"
            ),
            EvacuationCenterUpdate.remarks.label(
                "remarks"
            ),
            EvacuationCenterUpdate.recorded_at.label(
                "recorded_at"
            ),
            func.row_number().over(
                partition_by=(
                    EvacuationCenterUpdate.evacuation_center_id
                ),
                order_by=(
                    EvacuationCenterUpdate.recorded_at.desc(),
                    EvacuationCenterUpdate.id.desc(),
                ),
            ).label("row_rank"),
        )
        .join(
            EvacuationCenter,
            EvacuationCenter.id
            == EvacuationCenterUpdate.evacuation_center_id,
        )
        .where(*filters)
        .subquery()
    )

    statement = (
        select(
            ranked.c.id,
            ranked.c.evacuation_center_id,
            ranked.c.barangay_id,
            ranked.c.center_name,
            ranked.c.safe_capacity,
            ranked.c.status,
            ranked.c.families,
            ranked.c.individuals,
            ranked.c.children,
            ranked.c.senior_citizens,
            ranked.c.pwd,
            ranked.c.pregnant_women,
            ranked.c.medical_cases,
            ranked.c.food_status,
            ranked.c.water_status,
            ranked.c.electricity_status,
            ranked.c.sanitation_status,
            ranked.c.source,
            ranked.c.validation_status,
            ranked.c.remarks,
            ranked.c.recorded_at,
        )
        .where(ranked.c.row_rank == 1)
    )

    return session.execute(
        statement
    ).mappings().all()


def fetch_cross_allocation_by_submission_key(
    session: Session,
    *,
    submission_key: str,
) -> CrossBarangayEvacuationAllocation | None:
    return session.scalar(
        select(CrossBarangayEvacuationAllocation).where(
            CrossBarangayEvacuationAllocation.submission_key
            == submission_key
        )
    )


def _latest_cross_allocations_subquery(
    *,
    event_id: int,
):
    return (
        select(
            CrossBarangayEvacuationAllocation.id.label("id"),
            CrossBarangayEvacuationAllocation.event_id.label("event_id"),
            CrossBarangayEvacuationAllocation.evacuation_center_id.label(
                "evacuation_center_id"
            ),
            CrossBarangayEvacuationAllocation.origin_barangay_id.label(
                "origin_barangay_id"
            ),
            CrossBarangayEvacuationAllocation.families.label("families"),
            CrossBarangayEvacuationAllocation.individuals.label(
                "individuals"
            ),
            CrossBarangayEvacuationAllocation.source.label("source"),
            CrossBarangayEvacuationAllocation.remarks.label("remarks"),
            CrossBarangayEvacuationAllocation.recorded_by.label(
                "recorded_by"
            ),
            CrossBarangayEvacuationAllocation.recorded_at.label(
                "recorded_at"
            ),
            func.row_number().over(
                partition_by=(
                    CrossBarangayEvacuationAllocation.evacuation_center_id,
                    CrossBarangayEvacuationAllocation.origin_barangay_id,
                ),
                order_by=(
                    CrossBarangayEvacuationAllocation.recorded_at.desc(),
                    CrossBarangayEvacuationAllocation.id.desc(),
                ),
            ).label("row_rank"),
        )
        .where(
            CrossBarangayEvacuationAllocation.event_id == event_id
        )
        .subquery()
    )


def fetch_latest_cross_allocations_for_center(
    session: Session,
    *,
    event_id: int,
    center_id: int,
):
    ranked = _latest_cross_allocations_subquery(
        event_id=event_id
    )
    statement = (
        select(
            ranked.c.id,
            ranked.c.event_id,
            ranked.c.evacuation_center_id,
            ranked.c.origin_barangay_id,
            Barangay.name.label("origin_barangay_name"),
            ranked.c.families,
            ranked.c.individuals,
            ranked.c.source,
            ranked.c.remarks,
            ranked.c.recorded_by,
            ranked.c.recorded_at,
        )
        .join(
            Barangay,
            Barangay.id == ranked.c.origin_barangay_id,
        )
        .where(
            ranked.c.row_rank == 1,
            ranked.c.evacuation_center_id == center_id,
        )
        .order_by(Barangay.name)
    )
    return session.execute(statement).mappings().all()


def fetch_latest_cross_allocations_for_event(
    session: Session,
    *,
    event_id: int,
):
    ranked = _latest_cross_allocations_subquery(
        event_id=event_id
    )
    origin_barangay = Barangay.__table__.alias(
        "origin_barangay"
    )
    statement = (
        select(
            ranked.c.id,
            ranked.c.event_id,
            ranked.c.evacuation_center_id,
            EvacuationCenter.name.label("center_name"),
            EvacuationCenter.barangay_id.label("host_barangay_id"),
            ranked.c.origin_barangay_id,
            origin_barangay.c.name.label("origin_barangay_name"),
            ranked.c.families,
            ranked.c.individuals,
            ranked.c.source,
            ranked.c.remarks,
            ranked.c.recorded_by,
            ranked.c.recorded_at,
        )
        .join(
            EvacuationCenter,
            EvacuationCenter.id == ranked.c.evacuation_center_id,
        )
        .join(
            origin_barangay,
            origin_barangay.c.id == ranked.c.origin_barangay_id,
        )
        .where(ranked.c.row_rank == 1)
        .order_by(
            EvacuationCenter.name,
            origin_barangay.c.name,
        )
    )
    return session.execute(statement).mappings().all()



def fetch_report_snapshot_by_generation_key(
    session: Session,
    *,
    generation_key: str,
) -> ReportSnapshot | None:
    return session.scalar(
        select(ReportSnapshot).where(
            ReportSnapshot.generation_key == generation_key
        )
    )


def fetch_report_snapshot_by_id(
    session: Session,
    *,
    snapshot_id: int,
) -> ReportSnapshot | None:
    return session.scalar(
        select(ReportSnapshot).where(
            ReportSnapshot.id == snapshot_id
        )
    )


def fetch_recent_report_snapshots(
    session: Session,
    *,
    limit: int = 100,
):
    statement = (
        select(
            ReportSnapshot.id,
            ReportSnapshot.event_id,
            DisasterEvent.event_name,
            DisasterEvent.classification,
            ReportSnapshot.report_type,
            ReportSnapshot.report_mode,
            ReportSnapshot.sitrep_number,
            ReportSnapshot.generated_by,
            ReportSnapshot.generated_at,
            ReportSnapshot.snapshot_sha256,
        )
        .join(
            DisasterEvent,
            DisasterEvent.id == ReportSnapshot.event_id,
        )
        .order_by(
            ReportSnapshot.generated_at.desc(),
            ReportSnapshot.id.desc(),
        )
        .limit(limit)
    )

    return session.execute(statement).mappings().all()
