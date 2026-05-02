"""``medication_interactions`` — symmetric drug-cooldown pairs (D5).

A single row ``(A, B, N)`` carries both directions semantically.  Phase 6
enforces the actual cooldown logic; Phase 1 just stores the table.

Uniqueness on the *unordered* pair is enforced via a UNIQUE expression
index on ``(LEAST, GREATEST)``.  Declared on the model so ``alembic
check`` does not see it as drift.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, func
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


# UNIQUE on the unordered pair (LEAST, GREATEST).  Declared at module
# scope (not inside __table_args__) so the column references resolve to
# the post-class Column objects, matching ``ix_users_email_lower``.
Index(
    "ix_medication_interactions_pair",
    func.least(
        MedicationInteraction.medication_id,
        MedicationInteraction.conflicting_medication_id,
    ),
    func.greatest(
        MedicationInteraction.medication_id,
        MedicationInteraction.conflicting_medication_id,
    ),
    unique=True,
)
