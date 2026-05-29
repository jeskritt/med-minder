"""add admin_audit_log

Revision ID: 0007_admin_audit_log
Revises: 0006_reminder_indexes
Create Date: 2026-05-28 13:23:39.813340

Feature 009 (In-app admin user management) adds one append-only table,
``admin_audit_log`` — one row per successful privileged admin action
(create/update/role_change/password_reset/deactivate). FKs to ``users`` carry
no ``ON DELETE CASCADE`` so history outlives a soft-deleted actor/target.

The ``admin_audit_action`` enum is created/dropped explicitly (matching the
Phase 1 baseline convention) so a downgrade leaves no orphan type that would
break a re-upgrade.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007_admin_audit_log"
down_revision: str | None = "0006_reminder_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    admin_audit_action = postgresql.ENUM(
        "create",
        "update",
        "role_change",
        "password_reset",
        "deactivate",
        name="admin_audit_action",
    )
    admin_audit_action.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "admin_audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "target_user_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "action",
            postgresql.ENUM(name="admin_audit_action", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_audit_log_actor_id"),
        "admin_audit_log",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_audit_log_target_user_id"),
        "admin_audit_log",
        ["target_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_admin_audit_log_target_user_id"), table_name="admin_audit_log"
    )
    op.drop_index(
        op.f("ix_admin_audit_log_actor_id"), table_name="admin_audit_log"
    )
    op.drop_table("admin_audit_log")
    op.execute("DROP TYPE IF EXISTS admin_audit_action")
