"""``doses`` — append-only audit trail of medication taken events.

``user_id`` is denormalized (D4) so adherence queries avoid the join.
The cross-table invariant ``doses.user_id == medications.user_id`` is
enforced by a Postgres trigger declared in the Alembic migration, not
in Python.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from medminder.db import Base
from medminder.db.types import created_at_col, uuid_pk


class Dose(Base):
    __tablename__ = "doses"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    medication_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("medications.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("schedules.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    taken_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_doses_quantity_pos"),
    )
