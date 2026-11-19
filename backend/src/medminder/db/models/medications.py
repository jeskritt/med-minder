"""``medications`` table — per-user medication records.

Soft-deleted via ``deleted_at``; inventory tracked via three fields
(``total_doses_filled``, ``doses_remaining``, ``total_doses``) per D12.
Cross-column CHECK enforces that timer modes requiring extra fields
have them set.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Numeric,
    Select,
    SmallInteger,
    Text,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from medminder.db import Base
from medminder.db.types import created_at_col, deleted_at_col, updated_at_col, uuid_pk

TimerPreference = Literal["none", "count_up", "count_down", "multi_sub_dose"]


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    times_per_day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    quantity_per_dose: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    # Pill-based dosage (UX enhancements): when both are set, the
    # medication is "pill-based" and `quantity_per_dose` is derived
    # server-side (`pill_strength * pills_per_dose`). Both null →
    # quantity-based (the historical model).
    pill_strength: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3), nullable=True
    )
    pills_per_dose: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    # multi_sub_dose two-cap: when set with timer_preference=multi_sub_dose,
    # `create_dose` enforces an extra "max non-voided doses today" guard
    # alongside the per-window slot cap (`times_per_day`).
    max_doses_per_day: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_doses: Mapped[int | None] = mapped_column(nullable=True)
    timer_preference: Mapped[TimerPreference] = mapped_column(
        Enum(
            "none",
            "count_up",
            "count_down",
            "multi_sub_dose",
            name="timer_preference",
        ),
        nullable=False,
    )
    min_interval_minutes: Mapped[int | None] = mapped_column(nullable=True)
    window_duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    total_doses_filled: Mapped[int] = mapped_column(nullable=False, server_default="0")
    doses_remaining: Mapped[int] = mapped_column(nullable=False, server_default="0")
    refill_count: Mapped[int | None] = mapped_column(nullable=True)
    refill_threshold: Mapped[int | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime | None] = deleted_at_col()
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        CheckConstraint(
            "times_per_day >= 0", name="ck_medications_times_per_day_nonneg"
        ),
        CheckConstraint(
            "quantity_per_dose > 0", name="ck_medications_quantity_per_dose_pos"
        ),
        CheckConstraint(
            "total_doses IS NULL OR total_doses > 0",
            name="ck_medications_total_doses_pos",
        ),
        CheckConstraint(
            "total_doses_filled >= 0",
            name="ck_medications_total_doses_filled_nonneg",
        ),
        CheckConstraint(
            "doses_remaining >= 0", name="ck_medications_doses_remaining_nonneg"
        ),
        CheckConstraint(
            "refill_count IS NULL OR refill_count >= 0",
            name="ck_medications_refill_count_nonneg",
        ),
        CheckConstraint(
            "refill_threshold IS NULL OR refill_threshold >= 0",
            name="ck_medications_refill_threshold_nonneg",
        ),
        CheckConstraint(
            "(timer_preference <> 'count_down') "
            "OR (min_interval_minutes IS NOT NULL AND min_interval_minutes > 0)",
            name="ck_medications_count_down_requires_interval",
        ),
        CheckConstraint(
            "(timer_preference <> 'multi_sub_dose') "
            "OR (window_duration_minutes IS NOT NULL "
            "AND window_duration_minutes > 0)",
            name="ck_medications_multi_sub_dose_requires_window",
        ),
        CheckConstraint(
            "pill_strength IS NULL OR pill_strength > 0",
            name="ck_medications_pill_strength_pos",
        ),
        CheckConstraint(
            "pills_per_dose IS NULL OR pills_per_dose >= 1",
            name="ck_medications_pills_per_dose_pos",
        ),
        CheckConstraint(
            "max_doses_per_day IS NULL OR max_doses_per_day >= 1",
            name="ck_medications_max_doses_per_day_pos",
        ),
        CheckConstraint(
            "(pill_strength IS NULL AND pills_per_dose IS NULL) "
            "OR (pill_strength IS NOT NULL AND pills_per_dose IS NOT NULL)",
            name="ck_medications_pill_strength_pills_paired",
        ),
    )


def active() -> Select[Medication]:
    """``select(Medication)`` filtered to non-soft-deleted rows."""
    return select(Medication).where(Medication.deleted_at.is_(None))
