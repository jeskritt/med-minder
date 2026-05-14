"""Pure-domain tests for ``compute_timer_state``.

Cases are loaded from ``fixtures/timer_cases.json`` so the same data
also drives the frontend vitest suite (T017).
"""

from __future__ import annotations

import json
from datetime import datetime
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
