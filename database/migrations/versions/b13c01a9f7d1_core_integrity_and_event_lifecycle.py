"""core integrity and event lifecycle

Revision ID: b13c01a9f7d1
Revises: 8e3e8bf10bb0
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b13c01a9f7d1"
down_revision: Union[str, Sequence[str], None] = "8e3e8bf10bb0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "disaster_events",
        sa.Column(
            "classification",
            sa.String(length=50),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_disaster_events_classification",
        "disaster_events",
        (
            "classification IS NULL OR classification IN ("
            "'Tropical Depression', "
            "'Tropical Storm', "
            "'Severe Tropical Storm', "
            "'Typhoon', "
            "'Super Typhoon')"
        ),
    )

    op.create_index(
        "uq_disaster_events_one_active",
        "disaster_events",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text(
            "is_active = true"
        ),
    )

    op.add_column(
        "alert_level_history",
        sa.Column(
            "changed_by_user_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "alert_level_history",
        sa.Column(
            "changed_by",
            sa.String(length=150),
            nullable=True,
        ),
    )

    op.create_index(
        op.f(
            "ix_alert_level_history_changed_by_user_id"
        ),
        "alert_level_history",
        ["changed_by_user_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_alert_level_history_changed_by_user_id",
        "alert_level_history",
        "app_users",
        ["changed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "event_change_history",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "change_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "field_name",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "previous_value",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "new_value",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "authority_reference",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "changed_by_user_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "changed_by",
            sa.String(length=150),
            nullable=True,
        ),
        sa.Column(
            "effective_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text(
                "now()"
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["app_users.id"],
            name="fk_event_change_history_changed_by_user_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["disaster_events.id"],
            name="fk_event_change_history_event_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id"
        ),
    )

    op.create_index(
        op.f(
            "ix_event_change_history_event_id"
        ),
        "event_change_history",
        ["event_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_event_change_history_changed_by_user_id"
        ),
        "event_change_history",
        ["changed_by_user_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_event_change_history_effective_at"
        ),
        "event_change_history",
        ["effective_at"],
        unique=False,
    )

    op.add_column(
        "barangay_updates",
        sa.Column(
            "submission_key",
            sa.String(length=36),
            nullable=True,
        ),
    )

    op.add_column(
        "barangay_updates",
        sa.Column(
            "submitted_by_user_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "barangay_updates",
        sa.Column(
            "submitted_by",
            sa.String(length=150),
            nullable=True,
        ),
    )

    op.create_unique_constraint(
        "uq_barangay_updates_submission_key",
        "barangay_updates",
        ["submission_key"],
    )

    op.create_index(
        op.f(
            "ix_barangay_updates_submitted_by_user_id"
        ),
        "barangay_updates",
        ["submitted_by_user_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_barangay_updates_submitted_by_user_id",
        "barangay_updates",
        "app_users",
        ["submitted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "evacuation_center_updates",
        sa.Column(
            "submission_key",
            sa.String(length=36),
            nullable=True,
        ),
    )

    op.add_column(
        "evacuation_center_updates",
        sa.Column(
            "submitted_by_user_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "evacuation_center_updates",
        sa.Column(
            "submitted_by",
            sa.String(length=150),
            nullable=True,
        ),
    )

    op.create_unique_constraint(
        "uq_evacuation_updates_submission_key",
        "evacuation_center_updates",
        ["submission_key"],
    )

    op.create_index(
        op.f(
            "ix_evacuation_center_updates_submitted_by_user_id"
        ),
        "evacuation_center_updates",
        ["submitted_by_user_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_evacuation_center_updates_submitted_by_user_id",
        "evacuation_center_updates",
        "app_users",
        ["submitted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_evacuation_center_updates_submitted_by_user_id",
        "evacuation_center_updates",
        type_="foreignkey",
    )

    op.drop_index(
        op.f(
            "ix_evacuation_center_updates_submitted_by_user_id"
        ),
        table_name="evacuation_center_updates",
    )

    op.drop_constraint(
        "uq_evacuation_updates_submission_key",
        "evacuation_center_updates",
        type_="unique",
    )

    op.drop_column(
        "evacuation_center_updates",
        "submitted_by",
    )

    op.drop_column(
        "evacuation_center_updates",
        "submitted_by_user_id",
    )

    op.drop_column(
        "evacuation_center_updates",
        "submission_key",
    )

    op.drop_constraint(
        "fk_barangay_updates_submitted_by_user_id",
        "barangay_updates",
        type_="foreignkey",
    )

    op.drop_index(
        op.f(
            "ix_barangay_updates_submitted_by_user_id"
        ),
        table_name="barangay_updates",
    )

    op.drop_constraint(
        "uq_barangay_updates_submission_key",
        "barangay_updates",
        type_="unique",
    )

    op.drop_column(
        "barangay_updates",
        "submitted_by",
    )

    op.drop_column(
        "barangay_updates",
        "submitted_by_user_id",
    )

    op.drop_column(
        "barangay_updates",
        "submission_key",
    )

    op.drop_index(
        op.f(
            "ix_event_change_history_effective_at"
        ),
        table_name="event_change_history",
    )

    op.drop_index(
        op.f(
            "ix_event_change_history_changed_by_user_id"
        ),
        table_name="event_change_history",
    )

    op.drop_index(
        op.f(
            "ix_event_change_history_event_id"
        ),
        table_name="event_change_history",
    )

    op.drop_table(
        "event_change_history"
    )

    op.drop_constraint(
        "fk_alert_level_history_changed_by_user_id",
        "alert_level_history",
        type_="foreignkey",
    )

    op.drop_index(
        op.f(
            "ix_alert_level_history_changed_by_user_id"
        ),
        table_name="alert_level_history",
    )

    op.drop_column(
        "alert_level_history",
        "changed_by",
    )

    op.drop_column(
        "alert_level_history",
        "changed_by_user_id",
    )

    op.drop_index(
        "uq_disaster_events_one_active",
        table_name="disaster_events",
    )

    op.drop_constraint(
        "ck_disaster_events_classification",
        "disaster_events",
        type_="check",
    )

    op.drop_column(
        "disaster_events",
        "classification",
    )
