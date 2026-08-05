from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AlertLevel(Base):
    __tablename__ = "alert_levels"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    code: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    color_hex: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class DisasterEvent(Base):
    __tablename__ = "disaster_events"

    __table_args__ = (
        CheckConstraint(
            """
            eoc_status IN (
                'Monitoring',
                'Partially Activated',
                'Activated',
                'Stand Down'
            )
            """,
            name="ck_disaster_events_eoc_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    event_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    hazard_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    current_alert_level_id: Mapped[int] = mapped_column(
        ForeignKey(
            "alert_levels.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    eoc_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Monitoring",
        server_default="Monitoring",
    )

    current_sitrep_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    official_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    situation_overview: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AlertLevelHistory(Base):
    __tablename__ = "alert_level_history"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey(
            "disaster_events.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    previous_alert_level_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "alert_levels.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    new_alert_level_id: Mapped[int] = mapped_column(
        ForeignKey(
            "alert_levels.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    authority_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Barangay(Base):
    __tablename__ = "barangays"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    psgc_code: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class BarangayUpdate(Base):
    __tablename__ = "barangay_updates"

    __table_args__ = (
        CheckConstraint(
            """
            situation_status IN (
                'No Report',
                'Normal',
                'Monitoring',
                'Affected',
                'Critical'
            )
            """,
            name="ck_barangay_updates_situation_status",
        ),
        CheckConstraint(
            """
            road_status IN (
                'Unknown',
                'Passable',
                'Passable to Large Vehicles Only',
                'Limited Access',
                'Impassable'
            )
            """,
            name="ck_barangay_updates_road_status",
        ),
        CheckConstraint(
            """
            power_status IN (
                'Unknown',
                'Normal',
                'Partial',
                'Interrupted'
            )
            """,
            name="ck_barangay_updates_power_status",
        ),
        CheckConstraint(
            """
            water_status IN (
                'Unknown',
                'Normal',
                'Partial',
                'Interrupted'
            )
            """,
            name="ck_barangay_updates_water_status",
        ),
        CheckConstraint(
            """
            validation_status IN (
                'Draft',
                'Submitted',
                'For Validation',
                'Validated',
                'Needs Correction',
                'Superseded'
            )
            """,
            name="ck_barangay_updates_validation_status",
        ),
        CheckConstraint(
            """
            affected_families >= 0
            AND affected_individuals >= 0
            AND inside_ec_families >= 0
            AND inside_ec_individuals >= 0
            AND outside_ec_families >= 0
            AND outside_ec_individuals >= 0
            AND flood_depth_cm >= 0
            AND rescue_requests >= 0
            """,
            name="ck_barangay_updates_nonnegative_counts",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey(
            "disaster_events.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    barangay_id: Mapped[int] = mapped_column(
        ForeignKey(
            "barangays.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    situation_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    affected_families: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    affected_individuals: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    inside_ec_families: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    inside_ec_individuals: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    outside_ec_families: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    outside_ec_individuals: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    flood_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Unknown",
        server_default="Unknown",
    )

    flood_depth_cm: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    road_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Unknown",
        server_default="Unknown",
    )

    power_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Unknown",
        server_default="Unknown",
    )

    water_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Unknown",
        server_default="Unknown",
    )

    rescue_requests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    source: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    validation_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Submitted",
        server_default="Submitted",
    )

    remarks: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EvacuationCenter(Base):
    __tablename__ = "evacuation_centers"

    __table_args__ = (
        UniqueConstraint(
            "name",
            "barangay_id",
            name="uq_evacuation_centers_name_barangay",
        ),
        CheckConstraint(
            "safe_capacity >= 0",
            name="ck_evacuation_centers_capacity",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    barangay_id: Mapped[int] = mapped_column(
        ForeignKey(
            "barangays.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    address: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    safe_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EvacuationCenterUpdate(Base):
    __tablename__ = "evacuation_center_updates"

    __table_args__ = (
        CheckConstraint(
            """
            status IN (
                'Standby',
                'Open',
                'Full',
                'Over Capacity',
                'Closed'
            )
            """,
            name="ck_evacuation_updates_status",
        ),
        CheckConstraint(
            """
            food_status IN (
                'Unknown',
                'Sufficient',
                'Low',
                'Critical',
                'Unavailable'
            )
            """,
            name="ck_evacuation_updates_food_status",
        ),
        CheckConstraint(
            """
            water_status IN (
                'Unknown',
                'Sufficient',
                'Low',
                'Critical',
                'Unavailable'
            )
            """,
            name="ck_evacuation_updates_water_status",
        ),
        CheckConstraint(
            """
            electricity_status IN (
                'Unknown',
                'Available',
                'Partial',
                'Unavailable'
            )
            """,
            name="ck_evacuation_updates_electricity_status",
        ),
        CheckConstraint(
            """
            validation_status IN (
                'Draft',
                'Submitted',
                'For Validation',
                'Validated',
                'Needs Correction',
                'Superseded'
            )
            """,
            name="ck_evacuation_updates_validation_status",
        ),
        CheckConstraint(
            """
            families >= 0
            AND individuals >= 0
            AND children >= 0
            AND senior_citizens >= 0
            AND pwd >= 0
            AND pregnant_women >= 0
            AND medical_cases >= 0
            """,
            name="ck_evacuation_updates_nonnegative_counts",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey(
            "disaster_events.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    evacuation_center_id: Mapped[int] = mapped_column(
        ForeignKey(
            "evacuation_centers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    families: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    individuals: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    children: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    senior_citizens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    pwd: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    pregnant_women: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    medical_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    food_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Unknown",
        server_default="Unknown",
    )

    water_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Unknown",
        server_default="Unknown",
    )

    electricity_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Unknown",
        server_default="Unknown",
    )

    sanitation_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Unknown",
        server_default="Unknown",
    )

    source: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    validation_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Submitted",
        server_default="Submitted",
    )

    remarks: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Incident(Base):
    __tablename__ = "incidents"

    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "control_number",
            name="uq_incidents_event_control_number",
        ),
        CheckConstraint(
            """
            priority IN (
                'Low',
                'Moderate',
                'High',
                'Critical'
            )
            """,
            name="ck_incidents_priority",
        ),
        CheckConstraint(
            """
            status IN (
                'Reported',
                'For Verification',
                'Verified',
                'Team Dispatched',
                'Responding',
                'Resolved',
                'Cancelled'
            )
            """,
            name="ck_incidents_status",
        ),
        CheckConstraint(
            """
            validation_status IN (
                'Draft',
                'Submitted',
                'For Validation',
                'Validated',
                'Needs Correction',
                'Superseded'
            )
            """,
            name="ck_incidents_validation_status",
        ),
        CheckConstraint(
            "persons_affected >= 0",
            name="ck_incidents_persons_affected",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey(
            "disaster_events.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    control_number: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    barangay_id: Mapped[int] = mapped_column(
        ForeignKey(
            "barangays.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    exact_location: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    incident_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    persons_affected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Reported",
        server_default="Reported",
    )

    assigned_team: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    assigned_vehicle: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    action_taken: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    validation_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Submitted",
        server_default="Submitted",
    )

    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )