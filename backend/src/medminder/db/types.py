"""Shared column factories.

These helpers exist to keep model files terse and consistent.  Every
table uses the same UUID PK + ``created_at`` / ``updated_at`` columns
declared the same way, so they live in one place.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


def uuid_pk() -> Mapped[uuid.UUID]:
    """Postgres UUID primary key with ``gen_random_uuid()`` default."""
    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


def created_at_col() -> Mapped[datetime]:
    """``created_at TIMESTAMPTZ NOT NULL DEFAULT now()``."""
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


def updated_at_col() -> Mapped[datetime]:
    """``updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`` with onupdate."""
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


def deleted_at_col() -> Mapped[datetime | None]:
    """Nullable ``deleted_at TIMESTAMPTZ`` for soft delete."""
    return mapped_column(DateTime(timezone=True), nullable=True)
