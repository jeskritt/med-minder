"""Pure-domain tests for ``compute_timer_state``.

Cases are loaded from ``fixtures/timer_cases.json`` so the same data
also drives the frontend vitest suite (T017).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from medminder.domain.timers import compute_timer_state

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
    assert (
        state.multi_sub_dose.window_duration_seconds
        == payload["window_duration_seconds"]
    )
    assert state.multi_sub_dose.slots_total == payload["slots_total"]
    assert (
        state.multi_sub_dose.previous_window_unused_slots
        == payload["previous_window_unused_slots"]
    )

    expected_window = payload["active_window"]
    if expected_window is None:
        assert state.multi_sub_dose.active_window is None
    else:
        win = state.multi_sub_dose.active_window
        assert win is not None
        assert win.window_start == datetime.fromisoformat(
            expected_window["window_start"]
        )
        assert win.window_end == datetime.fromisoformat(
            expected_window["window_end"]
        )
        assert win.doses_in_window == [
            datetime.fromisoformat(d)
            for d in expected_window["doses_in_window"]
        ]
        assert win.slots_used == expected_window["slots_used"]
        assert win.slots_remaining == expected_window["slots_remaining"]


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
