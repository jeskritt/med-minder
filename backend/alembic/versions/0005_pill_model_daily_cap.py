"""ux: pill model + multi_sub_dose daily cap

Revision ID: 0005_pill_model_daily_cap
Revises: 0004_dose_interaction_overrides
Create Date: 2026-05-21 00:00:00.000000

Pre-Phase-7 usability batch. Adds three optional columns to
`medications`:

- `pill_strength` + `pills_per_dose` — when both set, the medication
  is "pill-based" and the existing `quantity_per_dose` is derived
  server-side (`= pill_strength * pills_per_dose`). Refill counts
  shift to pills semantically (same columns, mode-aware UI copy).
- `max_doses_per_day` — second cap for `multi_sub_dose` meds, on top
  of the per-window slot cap (`times_per_day`).

CHECKs:
- per-column positivity (NULL-tolerant).
- pill_strength ↔ pills_per_dose are paired (both null OR both set).
- `max_doses_per_day` cross-mode constraint is validation-only (no DB
  CHECK) to keep the per-mode rule editable in app code.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_pill_model_daily_cap"
down_revision: str | None = "0004_dose_interaction_overrides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "medications",
        sa.Column(
            "pill_strength",
            sa.Numeric(precision=10, scale=3),
            nullable=True,
        ),
    )
    op.add_column(
        "medications",
        sa.Column("pills_per_dose", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "medications",
        sa.Column("max_doses_per_day", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_medications_pill_strength_pos",
        "medications",
        "pill_strength IS NULL OR pill_strength > 0",
    )
    op.create_check_constraint(
        "ck_medications_pills_per_dose_pos",
        "medications",
        "pills_per_dose IS NULL OR pills_per_dose >= 1",
    )
    op.create_check_constraint(
        "ck_medications_max_doses_per_day_pos",
        "medications",
        "max_doses_per_day IS NULL OR max_doses_per_day >= 1",
    )
    op.create_check_constraint(
        "ck_medications_pill_strength_pills_paired",
        "medications",
        "(pill_strength IS NULL AND pills_per_dose IS NULL) "
        "OR (pill_strength IS NOT NULL AND pills_per_dose IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_medications_pill_strength_pills_paired",
        "medications",
        type_="check",
    )
    op.drop_constraint(
        "ck_medications_max_doses_per_day_pos",
        "medications",
        type_="check",
    )
    op.drop_constraint(
        "ck_medications_pills_per_dose_pos",
        "medications",
        type_="check",
    )
    op.drop_constraint(
        "ck_medications_pill_strength_pos",
        "medications",
        type_="check",
    )
    op.drop_column("medications", "max_doses_per_day")
    op.drop_column("medications", "pills_per_dose")
    op.drop_column("medications", "pill_strength")
