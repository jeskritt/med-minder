"""Pure-function tests for medication input validation.

These tests exercise ``validate_medication_input`` without touching
the DB or HTTP — that's the Constitution Principle III boundary.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from medminder.domain.medications import (
    InvalidMedicationError,
    MedicationInput,
    validate_medication_input,
)


def _valid(**overrides: object) -> MedicationInput:
    base: dict[str, object] = {
        "name": "Ibuprofen",
        "quantity_per_dose": Decimal("200"),
        "unit": "mg",
        "times_per_day": 2,
        "schedules": [uuid.uuid4(), uuid.uuid4()],
        "start_date": date(2026, 5, 1),
        "end_date": date(2026, 5, 10),
        "total_doses": 20,
        "refill_count": 30,
        "refill_threshold": 5,
    }
    base.update(overrides)
    return MedicationInput(**base)  # type: ignore[arg-type]


def test_valid_payload_passes() -> None:
    validate_medication_input(_valid())


def test_blank_name_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="name"):
        validate_medication_input(_valid(name="   "))


def test_blank_unit_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="unit"):
        validate_medication_input(_valid(unit=""))


def test_zero_dosage_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="quantity_per_dose"):
        validate_medication_input(_valid(quantity_per_dose=Decimal("0")))


def test_negative_dosage_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="quantity_per_dose"):
        validate_medication_input(_valid(quantity_per_dose=Decimal("-1")))


def test_negative_times_per_day_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="times_per_day"):
        validate_medication_input(_valid(times_per_day=-1))


def test_end_before_start_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="end_date"):
        validate_medication_input(
            _valid(start_date=date(2026, 5, 10), end_date=date(2026, 5, 1)),
        )


def test_end_equal_to_start_allowed() -> None:
    validate_medication_input(
        _valid(start_date=date(2026, 5, 5), end_date=date(2026, 5, 5)),
    )


def test_only_start_date_allowed() -> None:
    validate_medication_input(_valid(end_date=None))


def test_only_end_date_allowed() -> None:
    validate_medication_input(_valid(start_date=None))


def test_total_doses_none_means_untracked() -> None:
    validate_medication_input(_valid(total_doses=None))


def test_total_doses_zero_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="total_doses"):
        validate_medication_input(_valid(total_doses=0))


def test_total_doses_negative_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="total_doses"):
        validate_medication_input(_valid(total_doses=-3))


def test_negative_refill_count_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="refill_count"):
        validate_medication_input(_valid(refill_count=-1))


def test_negative_refill_threshold_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="refill_threshold"):
        validate_medication_input(_valid(refill_threshold=-1))


def test_refill_fields_optional() -> None:
    validate_medication_input(
        _valid(refill_count=None, refill_threshold=None),
    )


def test_zero_times_per_day_allowed_for_as_needed() -> None:
    validate_medication_input(
        _valid(times_per_day=0, schedules=[], total_doses=None),
    )


def test_multi_sub_dose_requires_times_per_day_at_least_one() -> None:
    with pytest.raises(InvalidMedicationError, match="times_per_day"):
        validate_medication_input(
            _valid(
                timer_preference="multi_sub_dose",
                window_duration_minutes=360,
                times_per_day=0,
            )
        )


def test_multi_sub_dose_valid_with_times_and_window() -> None:
    validate_medication_input(
        _valid(
            timer_preference="multi_sub_dose",
            window_duration_minutes=360,
            times_per_day=3,
        )
    )


# --- UX-enhancements: pill model + daily cap validation ----------------------


def test_pill_strength_without_pills_per_dose_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="together"):
        validate_medication_input(
            _valid(pill_strength=Decimal("100"), pills_per_dose=None)
        )


def test_pills_per_dose_without_strength_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="together"):
        validate_medication_input(
            _valid(pill_strength=None, pills_per_dose=2)
        )


def test_pill_strength_zero_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="pill_strength"):
        validate_medication_input(
            _valid(pill_strength=Decimal("0"), pills_per_dose=2)
        )


def test_pills_per_dose_zero_rejected() -> None:
    with pytest.raises(InvalidMedicationError, match="pills_per_dose"):
        validate_medication_input(
            _valid(pill_strength=Decimal("100"), pills_per_dose=0)
        )


def test_pill_model_valid_pair_passes() -> None:
    validate_medication_input(
        _valid(pill_strength=Decimal("100"), pills_per_dose=2)
    )


def test_max_doses_per_day_requires_multi_sub_dose() -> None:
    with pytest.raises(InvalidMedicationError, match="multi_sub_dose"):
        validate_medication_input(
            _valid(timer_preference="none", max_doses_per_day=4)
        )


def test_max_doses_per_day_must_be_at_least_times_per_day() -> None:
    with pytest.raises(InvalidMedicationError, match="times_per_day"):
        validate_medication_input(
            _valid(
                timer_preference="multi_sub_dose",
                window_duration_minutes=360,
                times_per_day=3,
                max_doses_per_day=2,
            )
        )


def test_max_doses_per_day_equal_to_times_per_day_allowed() -> None:
    validate_medication_input(
        _valid(
            timer_preference="multi_sub_dose",
            window_duration_minutes=360,
            times_per_day=3,
            max_doses_per_day=3,
        )
    )
