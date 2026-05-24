"""``reminders`` — pending or sent push notifications (D3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from medminder.db import Base
from medminder.db.types import created_at_col, updated_at_col, uuid_pk

ReminderType = Literal["dose", "refill"]
ReminderStatus = Literal["pending", "sent", "snoozed", "dismissed"]


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[ReminderType] = mapped_column(
        Enum("dose", "refill", name="reminder_type"),
        nullable=False,
    )
    medication_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("medications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("schedules.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(
            "pending",
            "sent",
            "snoozed",
            "dismissed",
            name="reminder_status",
        ),
        nullable=False,
        server_default="pending",
    )
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        CheckConstraint(
            "(type = 'dose' AND schedule_id IS NOT NULL "
            "AND medication_id IS NULL) "
            "OR (type = 'refill' AND medication_id IS NOT NULL "
            "AND schedule_id IS NULL)",
            name="ck_reminders_type_refs",
        ),
        # Hot dispatch scan: due `pending` rows ordered by fire time.
        Index(
            "ix_reminders_dispatch",
            "scheduled_for",
            postgresql_where=text("status = 'pending'"),
        ),
        # In-app reminder list (FR-008), scoped per user.
        Index("ix_reminders_user_status", "user_id", "status"),
        # At most one *open* refill warning per medication (FR-014): a
        # refill row is "open" until resolved (status <> 'dismissed').
        Index(
            "uq_reminders_open_refill",
            "medication_id",
            unique=True,
            postgresql_where=text("type = 'refill' AND status <> 'dismissed'"),
        ),
    )
