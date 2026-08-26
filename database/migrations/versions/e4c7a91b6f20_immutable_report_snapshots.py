"""add immutable report snapshots

Revision ID: e4c7a91b6f20
Revises: d7b2f91e4c31
Create Date: 2026-08-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e4c7a91b6f20"
down_revision: Union[str, Sequence[str], None] = "d7b2f91e4c31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("generation_key", sa.String(length=36), nullable=False),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column("report_mode", sa.String(length=40), nullable=False),
        sa.Column("sitrep_number", sa.String(length=30), nullable=True),
        sa.Column("generated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("generated_by", sa.String(length=150), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "report_type IN ('Situation Report')",
            name="ck_report_snapshots_report_type",
        ),
        sa.CheckConstraint(
            "report_mode IN ('Provisional Operational', 'Official Validated')",
            name="ck_report_snapshots_report_mode",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["disaster_events.id"],
            name="fk_report_snapshots_event_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["generated_by_user_id"],
            ["app_users.id"],
            name="fk_report_snapshots_generated_by_user_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "generation_key",
            name="uq_report_snapshots_generation_key",
        ),
    )

    op.create_index(
        "ix_report_snapshots_event_id",
        "report_snapshots",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        "ix_report_snapshots_generated_at",
        "report_snapshots",
        ["generated_at"],
        unique=False,
    )
    op.create_index(
        "ix_report_snapshots_generated_by_user_id",
        "report_snapshots",
        ["generated_by_user_id"],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION prevent_report_snapshot_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'report_snapshots are immutable; generate a new snapshot instead';
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_report_snapshots_immutable
        BEFORE UPDATE OR DELETE ON report_snapshots
        FOR EACH ROW
        EXECUTE FUNCTION prevent_report_snapshot_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_report_snapshots_immutable "
        "ON report_snapshots"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS prevent_report_snapshot_mutation()"
    )

    op.drop_index(
        "ix_report_snapshots_generated_by_user_id",
        table_name="report_snapshots",
    )
    op.drop_index(
        "ix_report_snapshots_generated_at",
        table_name="report_snapshots",
    )
    op.drop_index(
        "ix_report_snapshots_event_id",
        table_name="report_snapshots",
    )
    op.drop_table("report_snapshots")
