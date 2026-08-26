"""add immutable system audit log

Revision ID: f5a8d3c74211
Revises: e4c7a91b6f20
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f5a8d3c74211"
down_revision: Union[str, Sequence[str], None] = "e4c7a91b6f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AUDITED_TABLES = (
    "alert_levels",
    "disaster_events",
    "alert_level_history",
    "event_change_history",
    "barangay_updates",
    "evacuation_centers",
    "evacuation_center_updates",
    "incidents",
    "incident_history",
    "response_resources",
    "incident_resource_assignments",
    "cross_barangay_evacuation_allocations",
    "app_users",
    "report_snapshots",
)


def upgrade() -> None:
    op.create_table(
        "system_audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("table_name", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=10), nullable=False),
        sa.Column("record_id", sa.String(length=100), nullable=True),
        sa.Column("actor_snapshot", sa.String(length=200), nullable=True),
        sa.Column("old_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation IN ('INSERT', 'UPDATE', 'DELETE')",
            name="ck_system_audit_log_operation",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_system_audit_log_occurred_at",
        "system_audit_log",
        ["occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_system_audit_log_table_name",
        "system_audit_log",
        ["table_name"],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION mdrrmo_audit_row_change()
        RETURNS trigger AS $$
        DECLARE
            audit_actor text;
            audit_record_id text;
            row_payload jsonb;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                row_payload := to_jsonb(OLD);
            ELSE
                row_payload := to_jsonb(NEW);
            END IF;

            audit_actor := NULLIF(
                current_setting('mdrrmo.actor', true),
                ''
            );

            IF audit_actor IS NULL THEN
                audit_actor := COALESCE(
                    row_payload ->> 'reviewed_by',
                    row_payload ->> 'submitted_by',
                    row_payload ->> 'changed_by',
                    row_payload ->> 'reported_by',
                    row_payload ->> 'recorded_by',
                    row_payload ->> 'generated_by',
                    row_payload ->> 'assigned_by'
                );
            END IF;

            IF audit_actor IS NULL THEN
                audit_actor := 'database:' || current_user;
            END IF;

            audit_record_id := row_payload ->> 'id';

            INSERT INTO system_audit_log (
                table_name,
                operation,
                record_id,
                actor_snapshot,
                old_data,
                new_data,
                occurred_at
            )
            VALUES (
                TG_TABLE_NAME,
                TG_OP,
                audit_record_id,
                audit_actor,
                CASE WHEN TG_OP IN ('UPDATE', 'DELETE')
                     THEN to_jsonb(OLD) ELSE NULL END,
                CASE WHEN TG_OP IN ('INSERT', 'UPDATE')
                     THEN to_jsonb(NEW) ELSE NULL END,
                now()
            );

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    for table_name in AUDITED_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_audit_{table_name}
            AFTER INSERT OR UPDATE OR DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION mdrrmo_audit_row_change();
            """
        )

    op.execute(
        """
        CREATE FUNCTION prevent_system_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'system_audit_log is append-only and cannot be changed';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_system_audit_log_immutable
        BEFORE UPDATE OR DELETE ON system_audit_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_system_audit_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_system_audit_log_immutable ON system_audit_log"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS prevent_system_audit_mutation()"
    )

    for table_name in reversed(AUDITED_TABLES):
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_audit_{table_name} ON {table_name}"
        )

    op.execute(
        "DROP FUNCTION IF EXISTS mdrrmo_audit_row_change()"
    )
    op.drop_index(
        "ix_system_audit_log_table_name",
        table_name="system_audit_log",
    )
    op.drop_index(
        "ix_system_audit_log_occurred_at",
        table_name="system_audit_log",
    )
    op.drop_table("system_audit_log")
