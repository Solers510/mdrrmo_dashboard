from sqlalchemy import select
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