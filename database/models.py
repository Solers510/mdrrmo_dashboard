from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
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
        CheckConstraint(
            """
            classification IS NULL OR classification IN (
                'Tropical Depression',
                'Tropical Storm',
                'Severe Tropical Storm',
                'Typhoon',
                'Super Typhoon'
            )
            """,
            name="ck_disaster_events_classification",
        ),
        Index(
            "uq_disaster_events_one_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active = true"),
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

    classification: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
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

    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "app_users.id",
            name="fk_alert_level_history_changed_by_user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    changed_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EventChangeHistory(Base):
    __tablename__ = "event_change_history"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey(
            "disaster_events.id",
            name="fk_event_change_history_event_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    change_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    field_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    previous_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    new_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    authority_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "app_users.id",
            name="fk_event_change_history_changed_by_user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    changed_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
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
        UniqueConstraint(
            "submission_key",
            name="uq_barangay_updates_submission_key",
        ),
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

    supersedes_update_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "barangay_updates.id",
            name="fk_barangay_updates_supersedes_update_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    submission_key: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    submitted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "app_users.id",
            name="fk_barangay_updates_submitted_by_user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    submitted_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
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
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "app_users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    review_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
        UniqueConstraint(
            "submission_key",
            name="uq_evacuation_updates_submission_key",
        ),
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

    supersedes_update_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "evacuation_center_updates.id",
            name="fk_evacuation_center_updates_supersedes_update_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    submission_key: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    submitted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "app_users.id",
            name="fk_evacuation_center_updates_submitted_by_user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    submitted_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
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

    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "app_users.id",
            name="fk_evacuation_center_updates_reviewed_by_user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    reviewed_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    review_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
            "submission_key",
            name="uq_incidents_submission_key",
        ),
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

    submission_key: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    reported_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "app_users.id",
            name="fk_incidents_reported_by_user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    reported_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
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

class IncidentHistory(Base):
    __tablename__ = "incident_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey(
            "incidents.id",
            name="fk_incident_history_incident_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    field_name: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "app_users.id",
            name="fk_incident_history_changed_by_user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    changed_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ResponseResource(Base):
    __tablename__ = "response_resources"

    __table_args__ = (
        UniqueConstraint(
            "resource_code",
            name="uq_response_resources_code",
        ),
        CheckConstraint(
            "resource_type IN ('Response Team', 'Vehicle', 'Equipment')",
            name="ck_response_resources_type",
        ),
        CheckConstraint(
            "status IN ('Available', 'Assigned', 'Maintenance', 'Out of Service')",
            name="ck_response_resources_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(30), nullable=False)
    subtype: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Available",
        server_default="Available",
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


class IncidentResourceAssignment(Base):
    __tablename__ = "incident_resource_assignments"

    __table_args__ = (
        Index(
            "uq_active_incident_resource_assignment",
            "resource_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey(
            "incidents.id",
            name="fk_incident_resource_assignments_incident_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey(
            "response_resources.id",
            name="fk_incident_resource_assignments_resource_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    assigned_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "app_users.id",
            name="fk_incident_resource_assignments_assigned_by_user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    assigned_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CrossBarangayEvacuationAllocation(Base):
    __tablename__ = "cross_barangay_evacuation_allocations"

    __table_args__ = (
        UniqueConstraint(
            "submission_key",
            name="uq_cross_barangay_allocations_submission_key",
        ),
        CheckConstraint(
            "families >= 0 AND individuals >= 0 AND families <= individuals",
            name="ck_cross_barangay_allocation_counts",
        ),
        Index(
            "ix_cross_barangay_allocations_event_id",
            "event_id",
        ),
        Index(
            "ix_cross_barangay_allocations_center_id",
            "evacuation_center_id",
        ),
        Index(
            "ix_cross_barangay_allocations_origin_id",
            "origin_barangay_id",
        ),
        Index(
            "ix_cross_barangay_allocations_recorded_by_user_id",
            "recorded_by_user_id",
        ),
        Index(
            "ix_cross_barangay_allocations_recorded_at",
            "recorded_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey(
            "disaster_events.id",
            name="fk_cross_barangay_allocations_event_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    evacuation_center_id: Mapped[int] = mapped_column(
        ForeignKey(
            "evacuation_centers.id",
            name="fk_cross_barangay_allocations_center_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    origin_barangay_id: Mapped[int] = mapped_column(
        ForeignKey(
            "barangays.id",
            name="fk_cross_barangay_allocations_origin_barangay_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    submission_key: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
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
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "app_users.id",
            name="fk_cross_barangay_allocations_recorded_by_user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    recorded_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
class AppUser(Base):
    """
    An authorized MDRRMO dashboard user.

    Authentication is handled by the external OIDC provider.
    This table controls application authorization.
    """

    __tablename__ = "app_users"

    __table_args__ = (
        CheckConstraint(
            """
            role IN (
                'Viewer',
                'Executive',
                'Encoder',
                'Validator',
                'Operations Officer',
                'Administrator'
            )
            """,
            name="ck_app_users_role",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        unique=True,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Viewer",
        server_default="Viewer",
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