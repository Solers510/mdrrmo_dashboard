from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import (
    AlertLevel,
    Barangay,
    BarangayUpdate,
    DisasterEvent,
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
            DisasterEvent.eoc_status,
            DisasterEvent.current_sitrep_number,
            DisasterEvent.official_reference,
            DisasterEvent.situation_overview,
            DisasterEvent.started_at,
            DisasterEvent.created_at,
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