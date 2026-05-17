"""Pydantic schemas for ``POST /api/doses``."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DoseCreate(BaseModel):
    """Inbound payload for ``POST /api/doses``.

    ``user_id`` is intentionally absent — derived from the session.
    ``quantity`` defaults to ``medications.quantity_per_dose`` server-side
    when omitted.
    """

    model_config = ConfigDict(extra="forbid")

    medication_id: uuid.UUID
    schedule_id: uuid.UUID | None = None
    taken_at: datetime | None = None
    quantity: Decimal | None = None


class DoseRead(BaseModel):
    """Response shape for ``POST /api/doses`` and embedded under Today items."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    medication_id: uuid.UUID
    schedule_id: uuid.UUID | None
    taken_at: datetime
    quantity: Decimal
    created_at: datetime
