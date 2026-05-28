"""Append-only admin-action audit writer.

One helper, ``record_admin_action``, inserts a single ``admin_audit_log`` row
inside the caller's request transaction — so the audit entry commits atomically
with the action it describes (FR-013/SC-004). ``details`` is restricted to
changed **field names** by the call sites; this module never receives, stores,
or logs a password or hash (FR-020).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import AdminAuditLog
from medminder.db.models.admin_audit import AdminAuditAction


async def record_admin_action(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    action: AdminAuditAction,
    target_user_id: uuid.UUID,
    details: dict[str, Any] | None = None,
) -> AdminAuditLog:
    """Append one audit row; return the persisted entry.

    ``details`` should carry only non-secret descriptors (e.g.
    ``{"fields": ["name", "email"]}``); pass ``None`` for actions with nothing
    to summarize and an empty object is stored.
    """
    entry = AdminAuditLog(
        actor_id=actor_id,
        action=action,
        target_user_id=target_user_id,
        details=details if details is not None else {},
    )
    session.add(entry)
    await session.flush()
    return entry
