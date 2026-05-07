"""phase 3 refill inventory

Revision ID: 0002_phase_3_refill_inventory
Revises: 0001_phase_1_baseline
Create Date: 2026-05-07 00:00:00.000000

Adds nullable ``refill_count`` and ``refill_threshold`` columns to
``medications`` plus matching ``>= 0`` CHECKs.  Introduced by Phase 3
(Medications CRUD) — both columns are user-managed, optional, and have
no server default.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase_3_refill_inventory"
down_revision: str | None = "0001_phase_1_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "medications",
        sa.Column("refill_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "medications",
        sa.Column("refill_threshold", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_medications_refill_count_nonneg",
        "medications",
        "refill_count IS NULL OR refill_count >= 0",
    )
    op.create_check_constraint(
        "ck_medications_refill_threshold_nonneg",
        "medications",
        "refill_threshold IS NULL OR refill_threshold >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_medications_refill_threshold_nonneg", "medications", type_="check"
    )
    op.drop_constraint(
        "ck_medications_refill_count_nonneg", "medications", type_="check"
    )
    op.drop_column("medications", "refill_threshold")
    op.drop_column("medications", "refill_count")
