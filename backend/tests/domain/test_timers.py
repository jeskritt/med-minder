"""Pure-domain tests for ``compute_timer_state``.

Cases are loaded from ``fixtures/timer_cases.json`` so the same data
also drives the frontend vitest suite (T017).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from medminder.domain.timers import (
    COUNT_UP_ACTIVE_HORIZON_SECONDS,
    compute_timer_state,
    is_timer_active,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "timer_cases.json"
_CASES: dict[str, list[dict[str, Any]]] = json.loads(_FIXTURE.read_text())


def _make_med(payload: dict[str, Any]) -> Any:
    return SimpleNamespace(
        timer_preference=payload["timer_preference"],
        min_interval_minutes=payload.get("min_interval_minutes"),
        window_duration_minutes=payload.get("window_duration_minutes"),
        times_per_day=payload.get("times_per_day", 1),
    )


def _make_doses(rows: list[dict[str, Any]]) -> list[Any]:
    return [
        SimpleNamespace(taken_at=datetime.fromisoformat(r["taken_at"]))
        for r in rows
    ]


@pytest.mark.parametrize("case", _CASES["count_up"], ids=lambda c: c["name"])
def test_count_up_cases(case: dict[str, Any]) -> None:
    med = _make_med(case["med"])
    doses = _make_doses(case["doses"])
    now = datetime.fromisoformat(case["now"])

    state = compute_timer_state(med, doses, now=now)
    assert state is not None
    expected = case["expected"]
    assert state.mode == expected["mode"]

    expected_last = expected["last_dose_at"]
    if expected_last is None:
        assert state.last_dose_at is None
    else:
        assert state.last_dose_at == datetime.fromisoformat(expected_last)

    assert state.count_up is not None
    assert (
        state.count_up.elapsed_seconds == expected["count_up"]["elapsed_seconds"]
    )


@pytest.mark.parametrize("case", _CASES["count_down"], ids=lambda c: c["name"])
def test_count_down_cases(case: dict[str, Any]) -> None:
    med = _make_med(case["med"])
    doses = _make_doses(case["doses"])
    now = datetime.fromisoformat(case["now"])

    state = compute_timer_state(med, doses, now=now)
    assert state is not None
    expected = case["expected"]
    assert state.mode == expected["mode"]

    expected_last = expected["last_dose_at"]
    if expected_last is None:
        assert state.last_dose_at is None
    else:
        assert state.last_dose_at == datetime.fromisoformat(expected_last)

    assert state.count_down is not None
    payload = expected["count_down"]
    assert state.count_down.min_interval_seconds == payload["min_interval_seconds"]
    expected_next = payload["next_allowed_at"]
    if expected_next is None:
        assert state.count_down.next_allowed_at is None
    else:
        assert state.count_down.next_allowed_at == datetime.fromisoformat(
            expected_next
        )
    assert state.count_down.remaining_seconds == payload["remaining_seconds"]


@pytest.mark.parametrize(
    "case", _CASES["multi_sub_dose"], ids=lambda c: c["name"]
)
def test_multi_sub_dose_cases(case: dict[str, Any]) -> None:
    med = _make_med(case["med"])
    doses = _make_doses(case["doses"])
    now = datetime.fromisoformat(case["now"])

    state = compute_timer_state(med, doses, now=now)
    assert state is not None
    expected = case["expected"]
    assert state.mode == expected["mode"]

    expected_last = expected["last_dose_at"]
    if expected_last is None:
        assert state.last_dose_at is None
    else:
        assert state.last_dose_at == datetime.fromisoformat(expected_last)

    assert state.multi_sub_dose is not None
    payload = expected["multi_sub_dose"]
    msd = state.multi_sub_dose
    assert msd.window_duration_seconds == payload["window_duration_seconds"]
    assert msd.max_concurrent == payload["max_concurrent"]
    assert msd.slots_used == payload["slots_used"]
    assert msd.slots_remaining == payload["slots_remaining"]

    expected_next = payload["next_available_at"]
    if expected_next is None:
        assert msd.next_available_at is None
    else:
        assert msd.next_available_at == datetime.fromisoformat(expected_next)

    assert [(sd.taken_at, sd.expires_at) for sd in msd.active_sub_doses] == [
        (
            datetime.fromisoformat(d["taken_at"]),
            datetime.fromisoformat(d["expires_at"]),
        )
        for d in payload["active_sub_doses"]
    ]


_NOW = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)


def _state_for(
    med_payload: dict[str, Any],
    dose_ages_seconds: list[int],
) -> Any:
    """Build a TimerState from a med spec + dose ages (newest-first)."""
    med = _make_med(med_payload)
    doses = [
        SimpleNamespace(taken_at=_NOW - timedelta(seconds=age))
        for age in dose_ages_seconds
    ]
    return compute_timer_state(med, doses, now=_NOW)


def test_is_timer_active_none() -> None:
    assert is_timer_active(None) is False
    # timer_preference="none" yields no state, which is inactive.
    assert (
        compute_timer_state(_make_med({"timer_preference": "none"}), [], now=_NOW)
        is None
    )


def test_is_timer_active_count_down() -> None:
    med = {"timer_preference": "count_down", "min_interval_minutes": 60}
    # Dosed 10 min ago → 50 min still on the clock → running.
    assert is_timer_active(_state_for(med, [600])) is True
    # Dosed 2 h ago → interval elapsed → not running.
    assert is_timer_active(_state_for(med, [7200])) is False
    # Never dosed → nothing counting.
    assert is_timer_active(_state_for(med, [])) is False


def test_is_timer_active_multi_sub_dose() -> None:
    med = {
        "timer_preference": "multi_sub_dose",
        "window_duration_minutes": 360,
        "times_per_day": 3,
    }
    # One dose 1 h ago → still inside its rolling window → running.
    assert is_timer_active(_state_for(med, [3600])) is True
    # At capacity (3 doses still active) → running.
    assert is_timer_active(_state_for(med, [600, 1200, 1800])) is True
    # Last dose 7 h ago → its window has expired → not running.
    assert is_timer_active(_state_for(med, [7 * 3600])) is False
    # Never dosed → no active sub-dose.
    assert is_timer_active(_state_for(med, [])) is False


def test_is_timer_active_count_up_24h_horizon() -> None:
    med = {"timer_preference": "count_up"}
    # Within the 24 h horizon → running.
    assert is_timer_active(_state_for(med, [3600])) is True
    # Exactly at the horizon → still running (inclusive).
    assert (
        is_timer_active(_state_for(med, [COUNT_UP_ACTIVE_HORIZON_SECONDS])) is True
    )
    # One second past the horizon → expired.
    assert (
        is_timer_active(_state_for(med, [COUNT_UP_ACTIVE_HORIZON_SECONDS + 1]))
        is False
    )
    # Never dosed → elapsed is None → inactive.
    assert is_timer_active(_state_for(med, [])) is False


def test_multi_sub_dose_zero_times_per_day_degrades_to_none() -> None:
    """A misconfigured/legacy multi_sub_dose row (times_per_day < 1,
    slots_total would be 0) must NOT 500 the list/today — it degrades
    to no timer state so the medication still lists and is fixable.
    """
    med = _make_med(
        {
            "timer_preference": "multi_sub_dose",
            "window_duration_minutes": 360,
            "times_per_day": 0,
        }
    )
    assert (
        compute_timer_state(med, [], now=datetime(2026, 5, 18, tzinfo=UTC))
        is None
    )
