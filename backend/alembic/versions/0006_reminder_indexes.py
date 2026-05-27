"""phase 7: reminder dispatch/list indexes + refill dedup

Revision ID: 0006_reminder_indexes
Revises: 0005_pill_model_daily_cap
Create Date: 2026-05-24 00:00:00.000000

Phase 7 (Reminders) adds **no tables or columns** — the `reminders` and
`push_subscriptions` tables already exist from Phase 1. This revision adds
three indexes on `reminders`:

- `ix_reminders_dispatch` — partial on `scheduled_for` WHERE `status='pending'`,
  for the hot dispatch scan (due pending rows).
- `ix_reminders_user_status` — `(user_id, status)`, for the in-app list.
- `uq_reminders_open_refill` — partial UNIQUE on `medication_id` WHERE
  `type='refill' AND status <> 'dismissed'`, enforcing "at most one open
  refill warning per medication" (FR-014).

NOTE: the partial-index predicates must match the model's `postgresql_where`
text exactly for `alembic check` to report no drift — run
`alembic upgrade head && alembic check` after applying and adjust the WHERE
text here if the comparator flags a difference.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_reminder_indexes"
down_revision: str | None = "0005_pill_model_daily_cap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_reminders_dispatch",
        "reminders",
        ["scheduled_for"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_reminders_user_status",
        "reminders",
        ["user_id", "status"],
    )
    op.create_index(
        "uq_reminders_open_refill",
        "reminders",
        ["medication_id"],
        unique=True,
        postgresql_where=sa.text("type = 'refill' AND status <> 'dismissed'"),
    )


def downgrade() -> None:
    op.drop_index("uq_reminders_open_refill", table_name="reminders")
    op.drop_index("ix_reminders_user_status", table_name="reminders")
    op.drop_index("ix_reminders_dispatch", table_name="reminders")
