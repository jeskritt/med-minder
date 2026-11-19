"""``users`` table — authn principals managed by the admin CLI."""

from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Literal

from sqlalchemy import Enum, Index, Select, Text, Time, func, select
from sqlalchemy.orm import Mapped, mapped_column

from medminder.db import Base
from medminder.db.types import created_at_col, deleted_at_col, updated_at_col, uuid_pk

UserRole = Literal["admin", "user"]


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum("admin", "user", name="user_role"),
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    deleted_at: Mapped[datetime | None] = deleted_at_col()
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


# Functional UNIQUE on LOWER(email) — case-insensitive per D8.
Index(
    "ix_users_email_lower",
    func.lower(User.email),
    unique=True,
)


def active() -> Select[User]:
    """``select(User)`` filtered to non-soft-deleted rows."""
    return select(User).where(User.deleted_at.is_(None))
