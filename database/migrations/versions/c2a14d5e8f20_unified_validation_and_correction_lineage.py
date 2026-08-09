"""unified validation and correction lineage

Revision ID: c2a14d5e8f20
Revises: b13c01a9f7d1
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2a14d5e8f20"
down_revision: Union[str, Sequence[str], None] = "b13c01a9f7d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "barangay_updates",
        sa.Column("supersedes_update_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_barangay_updates_supersedes_update_id",
        "barangay_updates",
        ["supersedes_update_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_barangay_updates_supersedes_update_id",
        "barangay_updates",
        "barangay_updates",
        ["supersedes_update_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "evacuation_center_updates",
        sa.Column("supersedes_update_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_evacuation_center_updates_supersedes_update_id",
        "evacuation_center_updates",
        ["supersedes_update_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_evacuation_center_updates_supersedes_update_id",
        "evacuation_center_updates",
        "evacuation_center_updates",
        ["supersedes_update_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "evacuation_center_updates",
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "evacuation_center_updates",
        sa.Column("reviewed_by", sa.String(length=150), nullable=True),
    )
    op.add_column(
        "evacuation_center_updates",
        sa.Column("review_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "evacuation_center_updates",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_evacuation_center_updates_reviewed_by_user_id",
        "evacuation_center_updates",
        ["reviewed_by_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_evacuation_center_updates_reviewed_by_user_id",
        "evacuation_center_updates",
        "app_users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_evacuation_center_updates_reviewed_by_user_id",
        "evacuation_center_updates",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_evacuation_center_updates_reviewed_by_user_id",
        table_name="evacuation_center_updates",
    )
    op.drop_column("evacuation_center_updates", "reviewed_at")
    op.drop_column("evacuation_center_updates", "review_notes")
    op.drop_column("evacuation_center_updates", "reviewed_by")
    op.drop_column("evacuation_center_updates", "reviewed_by_user_id")

    op.drop_constraint(
        "fk_evacuation_center_updates_supersedes_update_id",
        "evacuation_center_updates",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_evacuation_center_updates_supersedes_update_id",
        table_name="evacuation_center_updates",
    )
    op.drop_column("evacuation_center_updates", "supersedes_update_id")

    op.drop_constraint(
        "fk_barangay_updates_supersedes_update_id",
        "barangay_updates",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_barangay_updates_supersedes_update_id",
        table_name="barangay_updates",
    )
    op.drop_column("barangay_updates", "supersedes_update_id")
