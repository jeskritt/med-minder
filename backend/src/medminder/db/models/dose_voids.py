"""``dose_voids`` — compensating-row record that a ``doses`` row is voided.

Phase 4 (ADR-0005). A ``doses`` row is **effective** iff no
``dose_voids`` row references it. The original dose is never updated
or deleted (D6).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from medminder.db import Base
from medminder.db.types import created_at_col, uuid_pk


class DoseVoid(Base):
    __tablename__ = "dose_voids"

    id: Mapped[uuid.UUID] = uuid_pk()
    dose_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("doses.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    voided_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    voided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = created_at_col()
