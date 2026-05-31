"""make admin_audit_log.actor_id nullable

Revision ID: 0008_audit_actor_nullable
Revises: 0007_admin_audit_log
Create Date: 2026-05-31 00:00:00.000000

Phase 10 hardening (G7): the admin CLI now also writes audit rows, but it has
no authenticated principal, so ``actor_id`` becomes nullable.  CLI rows record
``"via": "cli"`` in ``details`` instead.  The FK to ``users`` is unchanged.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008_audit_actor_nullable"
down_revision: str | None = "0007_admin_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "admin_audit_log",
        "actor_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "admin_audit_log",
        "actor_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
