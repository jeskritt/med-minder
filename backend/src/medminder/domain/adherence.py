"""Domain logic for long-term adherence views (Phase 9).

Everything here is **derived** from existing data — no new table (ADR-0016).

Two read paths:

- :func:`compute_medication_adherence` — per-day status
  (taken / partial / missed / future / inactive) for one medication across a
  date range, plus a window adherence percentage and course progress.
- :func:`iter_export_rows` — one row per non-voided dose across all the user's
  medications, for CSV export.

The pure classifiers (:func:`classify_day`, :func:`window_adherence_pct`) take
no DB session so they are unit-testable in isolation (Principle III). The
orchestration mirrors ``today_view``'s building blocks: the ``NOT EXISTS
(dose_voids)`` effective-dose filter and per-day bucketing in the user's IANA
zone.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from zoneinfo import ZoneInfo

from sqlalchemy import not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.db.models import (
    Dose,
    DoseVoid,
    Medication,
    Schedule,
    ScheduleMedication,
    User,
)
from medminder.domain.timezone import normalize_timezone

# A scheduled dose is "missed" only once its scheduled time plus this
# tolerance has passed with no recorded dose (ADR-0016 / spec FR-004).
MISSED_TOLERANCE = timedelta(hours=4)

# Guard on the requested window so a single request can't scan an unbounded
# range (spec FR-018). The UI requests at most a month/window at a time.
MAX_WINDOW_DAYS = 366


class AdherenceError(Exception):
    """Base for adherence-domain errors."""


class MedicationNotFoundError(AdherenceError):
    """Medication does not exist or is not owned by the user (HTTP 404)."""


class AdherenceRangeError(AdherenceError):
    """The requested date window is inverted or wider than the cap (HTTP 422)."""


class DayStatus(StrEnum):
    """Per-day adherence classification for one medication."""

    TAKEN = "taken"
    PARTIAL = "partial"
    MISSED = "missed"
    FUTURE = "future"
    INACTIVE = "inactive"


@dataclass(frozen=True)
class DayAdherence:
    """One local day's adherence for a medication."""

    date: date
    expected: int
    taken: int
    status: DayStatus


@dataclass(frozen=True)
class CourseProgress:
    """Doses-taken-of-course-size for a fixed-course medication."""

    total: int
    taken: int
    complete: bool


@dataclass(frozen=True)
class MedicationAdherence:
    """Windowed per-day adherence plus percentage and course progress."""

    medication_id: uuid.UUID
    timezone: str
    from_date: date
    to_date: date
    days: list[DayAdherence]
    adherence_pct: float | None
    course: CourseProgress | None


@dataclass(frozen=True)
class ExportRow:
    """One non-voided dose, flattened for CSV export."""

    medication_name: str
    taken_at: datetime
    quantity: Decimal
    unit: str
    schedule_label: str
    soft_deleted: bool


def classify_day(
    *,
    expected_slot_times: list[datetime],
    doses_count: int,
    now: datetime,
    tolerance: timedelta = MISSED_TOLERANCE,
) -> tuple[DayStatus, int, int]:
    """Classify one active day → ``(status, expected, taken_slots)``.

    ``expected_slot_times`` are the timezone-aware UTC instants of the slots
    scheduled on the day (already filtered by the schedule's days-of-week).
    ``doses_count`` is the number of non-voided doses recorded that day. A day
    outside the medication's active window is *inactive* and must be handled by
    the caller (it never reaches here).

    Pure: no DB, no clock — ``now`` is injected so tests are deterministic.
    """
    expected = len(expected_slot_times)
    if expected == 0:
        # PRN / off-schedule day: a dose makes it "taken", otherwise the day
        # simply isn't expected — never "missed" (FR-006). Excluded from the
        # percentage because expected == 0.
        return (DayStatus.TAKEN if doses_count > 0 else DayStatus.INACTIVE, 0, 0)

    taken_slots = min(doses_count, expected)
    if taken_slots >= expected:
        return (DayStatus.TAKEN, expected, expected)

    pending = [t for t in expected_slot_times if t + tolerance >= now]
    if taken_slots == 0:
        # No doses: fully future only while *every* slot is still within
        # tolerance; otherwise at least one slot is already missed.
        if len(pending) == expected:
            return (DayStatus.FUTURE, expected, 0)
        return (DayStatus.MISSED, expected, 0)
    return (DayStatus.PARTIAL, expected, taken_slots)


def window_adherence_pct(days: list[DayAdherence]) -> float | None:
    """Percentage over completed scheduled days, excluding inactive/future.

    ``(taken / expected) * 100`` summed across days whose status is
    taken/partial/missed and that have at least one expected slot, rounded to
    one decimal. Returns ``None`` when nothing is scored (PRN meds, or a window
    that is entirely future/inactive) — FR-014 / FR-017.
    """
    scored = {DayStatus.TAKEN, DayStatus.PARTIAL, DayStatus.MISSED}
    numerator = 0
    denominator = 0
    for day in days:
        if day.expected > 0 and day.status in scored:
            denominator += day.expected
            numerator += day.taken
    if denominator == 0:
        return None
    return round(numerator * 100 / denominator, 1)


def _date_range(from_date: date, to_date: date) -> Iterator[date]:
    current = from_date
    while current <= to_date:
        yield current
        current += timedelta(days=1)


async def compute_medication_adherence(
    session: AsyncSession,
    *,
    user: User,
    medication_id: uuid.UUID,
    from_date: date,
    to_date: date,
    timezone_override: str | None = None,
    now: datetime | None = None,
) -> MedicationAdherence:
    """Per-day adherence + percentage + course progress for one medication.

    Raises :class:`AdherenceRangeError` for an inverted or over-cap window and
    :class:`MedicationNotFoundError` when the medication is not the user's.
    Day bucketing uses the user's current zone (``timezone_override`` wins),
    consistent with ``today_view`` (D5).
    """
    if to_date < from_date:
        raise AdherenceRangeError("Range end is before its start.")
    if (to_date - from_date).days + 1 > MAX_WINDOW_DAYS:
        raise AdherenceRangeError(
            f"Range exceeds the {MAX_WINDOW_DAYS}-day cap.",
        )

    zone_name = normalize_timezone(timezone_override or user.timezone)
    zone = ZoneInfo(zone_name)
    now = now or datetime.now(UTC)

    med = (
        await session.execute(
            select(Medication).where(Medication.id == medication_id)
        )
    ).scalar_one_or_none()
    if med is None or med.user_id != user.id or med.deleted_at is not None:
        raise MedicationNotFoundError("Medication not found or not owned by user.")

    # Active, linked schedules for this medication (one slot each).
    schedules = list(
        (
            await session.execute(
                select(Schedule)
                .join(
                    ScheduleMedication,
                    ScheduleMedication.schedule_id == Schedule.id,
                )
                .where(
                    ScheduleMedication.medication_id == medication_id,
                    Schedule.user_id == user.id,
                    Schedule.deleted_at.is_(None),
                )
            )
        ).scalars()
    )

    # Local-day window → UTC bounds, then one query for the range.
    start_utc = datetime.combine(from_date, time(0, 0), tzinfo=zone).astimezone(UTC)
    end_utc = datetime.combine(
        to_date + timedelta(days=1), time(0, 0), tzinfo=zone
    ).astimezone(UTC)

    voided_exists = (
        select(DoseVoid.id).where(DoseVoid.dose_id == Dose.id).exists()
    )
    dose_times = list(
        (
            await session.execute(
                select(Dose.taken_at).where(
                    Dose.user_id == user.id,
                    Dose.medication_id == medication_id,
                    Dose.taken_at >= start_utc,
                    Dose.taken_at < end_utc,
                    not_(voided_exists),
                )
            )
        ).scalars()
    )
    doses_per_day: dict[date, int] = {}
    for taken_at in dose_times:
        local_day = taken_at.astimezone(zone).date()
        doses_per_day[local_day] = doses_per_day.get(local_day, 0) + 1

    days: list[DayAdherence] = []
    for day in _date_range(from_date, to_date):
        if (med.start_date is not None and day < med.start_date) or (
            med.end_date is not None and day > med.end_date
        ):
            days.append(
                DayAdherence(date=day, expected=0, taken=0, status=DayStatus.INACTIVE)
            )
            continue

        dow_bit = 1 << day.weekday()
        slot_times = [
            datetime.combine(day, s.time_of_day, tzinfo=zone).astimezone(UTC)
            for s in schedules
            if s.days_of_week & dow_bit
        ]
        status, expected, taken = classify_day(
            expected_slot_times=slot_times,
            doses_count=doses_per_day.get(day, 0),
            now=now,
        )
        days.append(
            DayAdherence(date=day, expected=expected, taken=taken, status=status)
        )

    course = await compute_course_progress(session, user=user, medication=med)

    return MedicationAdherence(
        medication_id=medication_id,
        timezone=zone_name,
        from_date=from_date,
        to_date=to_date,
        days=days,
        adherence_pct=window_adherence_pct(days),
        course=course,
    )


async def compute_course_progress(
    session: AsyncSession,
    *,
    user: User,
    medication: Medication,
) -> CourseProgress | None:
    """Non-voided dose count vs the medication's course size.

    Returns ``None`` when ``total_doses`` is unset. Window-independent and
    display-only — completion has no side effects (FR-008).
    """
    if medication.total_doses is None:
        return None

    voided_exists = (
        select(DoseVoid.id).where(DoseVoid.dose_id == Dose.id).exists()
    )
    taken = len(
        list(
            (
                await session.execute(
                    select(Dose.id).where(
                        Dose.user_id == user.id,
                        Dose.medication_id == medication.id,
                        not_(voided_exists),
                    )
                )
            ).scalars()
        )
    )
    return CourseProgress(
        total=medication.total_doses,
        taken=taken,
        complete=taken >= medication.total_doses,
    )


async def iter_export_rows(
    session: AsyncSession,
    *,
    user: User,
    timezone_override: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[ExportRow]:
    """The user's non-voided doses, flattened and oldest-first.

    Soft-deleted medications are included with their name suffixed
    " (removed)" so an old export stays coherent (FR-012). ``taken_at`` is
    rendered in the user's current zone (FR-013).

    ``from_date`` / ``to_date`` (inclusive, local days in the chosen zone)
    optionally bound the export to a window; both omitted exports the full
    history. An inverted range (``to_date < from_date``) raises
    :class:`AdherenceRangeError`. The zone is resolved even with no bounds so
    an unknown timezone surfaces consistently as :class:`InvalidTimezoneError`.
    """
    if from_date is not None and to_date is not None and to_date < from_date:
        raise AdherenceRangeError("Range end is before its start.")

    zone = ZoneInfo(normalize_timezone(timezone_override or user.timezone))
    voided_exists = (
        select(DoseVoid.id).where(DoseVoid.dose_id == Dose.id).exists()
    )

    conditions = [Dose.user_id == user.id, not_(voided_exists)]
    if from_date is not None:
        conditions.append(
            Dose.taken_at
            >= datetime.combine(from_date, time(0, 0), tzinfo=zone).astimezone(UTC)
        )
    if to_date is not None:
        conditions.append(
            Dose.taken_at
            < datetime.combine(
                to_date + timedelta(days=1), time(0, 0), tzinfo=zone
            ).astimezone(UTC)
        )

    rows = (
        await session.execute(
            select(
                Medication.name,
                Medication.unit,
                Medication.deleted_at,
                Dose.taken_at,
                Dose.quantity,
                Schedule.label,
            )
            .select_from(Dose)
            .join(Medication, Medication.id == Dose.medication_id)
            .outerjoin(Schedule, Schedule.id == Dose.schedule_id)
            .where(*conditions)
            .order_by(Dose.taken_at.asc())
        )
    ).all()

    out: list[ExportRow] = []
    for name, unit, deleted_at, taken_at, quantity, label in rows:
        soft_deleted = deleted_at is not None
        out.append(
            ExportRow(
                medication_name=f"{name} (removed)" if soft_deleted else name,
                taken_at=taken_at.astimezone(zone),
                quantity=quantity,
                unit=unit,
                schedule_label=label or "",
                soft_deleted=soft_deleted,
            )
        )
    return out


__all__ = [
    "MAX_WINDOW_DAYS",
    "MISSED_TOLERANCE",
    "AdherenceError",
    "AdherenceRangeError",
    "CourseProgress",
    "DayAdherence",
    "DayStatus",
    "ExportRow",
    "MedicationAdherence",
    "MedicationNotFoundError",
    "classify_day",
    "compute_course_progress",
    "compute_medication_adherence",
    "iter_export_rows",
    "window_adherence_pct",
]
