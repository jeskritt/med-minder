"""``admin_audit_log`` — append-only record of privileged admin actions.

One row per **successful** in-app admin user-management action (create, edit,
role change, password reset, deactivate), written in the same request
transaction as the action it describes (FR-013/SC-004). Append-only: no
``updated_at``/``deleted_at`` and no in-app edit/delete path (FR-022); entries
are retained indefinitely in this version. ``details`` carries changed **field
names** only — never passwords, hashes, or other secret values (FR-020).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from medminder.db import Base
from medminder.db.types import created_at_col, uuid_pk

AdminAuditAction = Literal[
    "create", "update", "role_change", "password_reset", "deactivate"
]


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[uuid.UUID] = uuid_pk()
    # No ON DELETE CASCADE: users are soft-deleted, and audit history must
    # outlive a deactivated actor or target.
    actor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    target_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    action: Mapped[AdminAuditAction] = mapped_column(
        Enum(
            "create",
            "update",
            "role_change",
            "password_reset",
            "deactivate",
            name="admin_audit_action",
        ),
        nullable=False,
    )
    # Changed field names only, e.g. {"fields": ["name", "email"]}; never
    # secret values.
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
