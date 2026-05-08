"""add dose_voids

Revision ID: 0003_add_dose_voids
Revises: 0002_phase_3_refill_inventory
Create Date: 2026-05-08 00:00:00.000000

Phase 4 — compensating-row "un-take" pattern (ADR-0005). Inserting into
``dose_voids`` marks the matching ``doses`` row as no-longer-effective
without violating Phase 1a D6 (``doses`` is append-only).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_add_dose_voids"
down_revision: str | None = "0002_phase_3_refill_inventory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dose_voids",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "dose_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("doses.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "voided_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_dose_voids_voided_by_user_id",
        "dose_voids",
        ["voided_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dose_voids_voided_by_user_id", table_name="dose_voids")
    op.drop_table("dose_voids")
