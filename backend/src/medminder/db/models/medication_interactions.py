"""``medication_interactions`` — symmetric drug-cooldown pairs (D5).

A single row ``(A, B, N)`` carries both directions semantically.  Phase 6
enforces the actual cooldown logic; Phase 1 just stores the table.

Uniqueness on the *unordered* pair is enforced via an expression index
(``LEAST/GREATEST``) added in the Alembic migration — autogenerate
cannot emit that, so the migration is hand-edited.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from medminder.db import Base
from medminder.db.types import created_at_col, uuid_pk


class MedicationInteraction(Base):
    __tablename__ = "medication_interactions"

    id: Mapped[uuid.UUID] = uuid_pk()
    medication_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("medications.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    conflicting_medication_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("medications.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cooldown_minutes: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        CheckConstraint(
            "cooldown_minutes > 0", name="ck_interactions_cooldown_pos"
        ),
        CheckConstraint(
            "medication_id <> conflicting_medication_id",
            name="ck_interactions_distinct_pair",
        ),
    )
