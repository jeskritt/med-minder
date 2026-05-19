"""phase 6: dose_interaction_overrides

Revision ID: 0004_dose_interaction_overrides
Revises: 0003_add_dose_voids
Create Date: 2026-05-18 00:00:00.000000

Phase 6 — append-only audit that a user was warned of an active
drug-interaction cooldown and explicitly proceeded (ADR-0008 /
ADR-0005 audit precedent). One row per (dose, conflicting medication);
never updated or deleted.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_dose_interaction_overrides"
down_revision: str | None = "0003_add_dose_voids"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dose_interaction_overrides",
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
        ),
        sa.Column(
            "conflicting_medication_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medications.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "dose_id",
            "conflicting_medication_id",
            name="uq_dose_interaction_override_pair",
        ),
    )
    op.create_index(
        "ix_dose_interaction_overrides_dose_id",
        "dose_interaction_overrides",
        ["dose_id"],
    )
    op.create_index(
        "ix_dose_interaction_overrides_conflicting_medication_id",
        "dose_interaction_overrides",
        ["conflicting_medication_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dose_interaction_overrides_conflicting_medication_id",
        table_name="dose_interaction_overrides",
    )
    op.drop_index(
        "ix_dose_interaction_overrides_dose_id",
        table_name="dose_interaction_overrides",
    )
    op.drop_table("dose_interaction_overrides")
