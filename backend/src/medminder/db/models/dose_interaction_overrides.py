"""``dose_interaction_overrides`` — append-only audit that a user was
warned of an active drug-interaction cooldown and explicitly proceeded.

Phase 6 (ADR-0008 / data-model D2). Written in the same transaction as
the acknowledged ``doses`` row, one row per (dose, conflicting
medication) that was in active conflict at acknowledgment time. Never
updated or deleted — same append-only / attributable stance as
``dose_voids`` (ADR-0005). Attribution is via ``doses.user_id`` of the
referenced dose (single-tenant).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from medminder.db import Base
from medminder.db.types import created_at_col, uuid_pk


class DoseInteractionOverride(Base):
    __tablename__ = "dose_interaction_overrides"

    id: Mapped[uuid.UUID] = uuid_pk()
    dose_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("doses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    conflicting_medication_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("medications.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint(
            "dose_id",
            "conflicting_medication_id",
            name="uq_dose_interaction_override_pair",
        ),
    )
