"""``schedule_medications`` — M:M association between schedules and meds."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from medminder.db import Base
from medminder.db.types import created_at_col


class ScheduleMedication(Base):
    __tablename__ = "schedule_medications"

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("schedules.id", ondelete="CASCADE"),
        primary_key=True,
    )
    medication_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("medications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = created_at_col()
