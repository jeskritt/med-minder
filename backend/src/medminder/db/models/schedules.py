"""``schedules`` — recurring time-of-day reminders (per D2 / D11)."""

from __future__ import annotations

import uuid
from datetime import datetime, time

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Select,
    SmallInteger,
    Time,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from medminder.db import Base
from medminder.db.types import created_at_col, deleted_at_col, updated_at_col, uuid_pk


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    time_of_day: Mapped[time] = mapped_column(Time, nullable=False)
    days_of_week: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="127"
    )
    label: Mapped[str] = mapped_column(nullable=False)
    deleted_at: Mapped[datetime | None] = deleted_at_col()
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        CheckConstraint(
            "days_of_week BETWEEN 0 AND 127",
            name="ck_schedules_days_of_week_range",
        ),
    )


def active() -> Select[tuple[Schedule]]:
    """``select(Schedule)`` filtered to non-soft-deleted rows."""
    return select(Schedule).where(Schedule.deleted_at.is_(None))
