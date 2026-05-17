# Phase 0 Research — Phase 5: Timer Modes

This document captures the design decisions made before implementation
begins. Each decision lists what was chosen, why, and what was rejected.

---

## D1 — Where timer logic lives

**Decision**: New module `backend/src/medminder/domain/timers.py`
holding `compute_timer_state(medication, doses, now) → TimerState`,
typed `TimerState` value classes (one dataclass per mode payload, with
a discriminated union at the top), and the
`MinIntervalNotElapsedError` exception class. The module imports only
the standard library plus `medminder.db.models.medications.Medication`
and `medminder.db.models.doses.Dose` for type hints — and even those
imports are shadowed by `if TYPE_CHECKING:` guards if necessary, so
at runtime the module has zero SQLAlchemy or FastAPI dependency.

**Rationale**: ADR-0004 mandates pure-function evaluation. Constitution
Principle III mandates testable units without DB or HTTP. Sister to
the existing `domain/passwords.py`, `domain/medications.py`,
`domain/doses.py` — same shape, same idioms.

**Alternatives considered**:
- *Single `services/` module mixing HTTP and logic.* Rejected —
  couples FastAPI to the math; fails Principle III.
- *State-machine library (`transitions` for Python, `xstate` for
  TypeScript).* Rejected — six functions of arithmetic do not justify
  a runtime dependency. ADR-0004's "Neutral" consequence already
  flags this.
- *Co-locating timer logic inside `domain/doses.py`.* Rejected —
  `doses.py` is the write path; timers are a read concern. Mixing them
  would force the read concern through the write path's session and
  validation infrastructure unnecessarily.

---

## D2 — Server response surface

**Decision**: Three deltas to the API:
1. Add `timer_state: TimerStateOut | None` to `TodayItem` in
   `backend/src/medminder/api/schemas/today.py`. Value is `None` when
   `medication.timer_preference == 'none'`.
2. Add `timer_state: TimerStateOut | None` to `MedicationOut` in
   `backend/src/medminder/api/schemas/medications.py`. Same null
   convention.
3. New endpoint `GET /api/v1/medications/{id}` returning a new
   `MedicationDetailOut` schema (initially equal in shape to
   `MedicationOut` so contracts can diverge cleanly later — Phase 6
   may add interaction-aware fields to detail-only).

`TimerStateOut` is the wire-format Pydantic model. The domain
`TimerState` value object is converted at the API boundary (in
`api/medications.py` / `api/schedules.py`) so domain code stays free
of `pydantic` imports.

**Rationale**: FR-001 requires timer state on every endpoint that
returns medication summaries. Today view and list exist; detail does
not. Billy's flow (`MultiSubDoseCard` with the FR-008b banner) needs a
detail page; that page needs an endpoint.

**Alternatives considered**:
- *Reuse `MedicationOut` directly for the detail endpoint.* Rejected
  — couples list and detail evolution; Phase 6 will likely diverge.
- *Embed `TimerState` inside `dose`.* Rejected — TimerState exists
  for medications without doses (e.g. a fresh `count_up` med shows
  "no doses recorded yet"); coupling them creates awkward null
  combinations.
- *Compute timer state on the client from raw doses.* Rejected — ADR-0004
  is server-authoritative for security (Harry's overdose guard) and
  consistency (Billy's window).

---

## D3 — Min-interval guard placement

**Decision**: Inside `create_dose()` in
`backend/src/medminder/domain/doses.py`, after the existing
ownership/schedule validation block (line 93) and before the `Dose(...)`
construction (line 97). Sketch:

```python
if med.timer_preference == "count_down":
    last = await _latest_non_voided_dose(session, medication_id)
    if last is not None and med.min_interval_minutes is not None:
        next_allowed = last.taken_at + timedelta(minutes=med.min_interval_minutes)
        if taken_at < next_allowed:
            raise MinIntervalNotElapsedError(
                medication_id=medication_id,
                next_allowed_at=next_allowed,
                remaining_seconds=int((next_allowed - taken_at).total_seconds()),
            )
```

A FastAPI exception handler (D6) maps this to **HTTP 409 Conflict**
with the JSON body specified in `MinIntervalViolation`.

**Rationale**: A single insertion point covers UI calls, direct API
calls, and any future CLI bulk-import path (FR-006). 409 because the
request is well-formed but conflicts with current state; 422 would
imply input malformedness.

**Alternatives considered**:
- *Client-side check only.* Rejected — fails FR-006 by design.
- *Pre-flight `enforce_count_down()` endpoint before the actual
  POST.* Rejected — TOCTOU race between check and write; doubles the
  round trips.
- *Check at the API boundary in `api/doses.py`.* Rejected — would have
  to reach into the domain layer for the latest dose anyway; cleaner
  to place the guard alongside the write that needs to be guarded.

---

## D4 — Client-side counter parity

**Decision**: Hand-ported TypeScript helper in
`frontend/src/lib/timers.ts`, paired with a shared JSON fixture file
at `backend/tests/domain/fixtures/timer_cases.json`. The fixture is
also imported by `frontend/src/__tests__/timers.test.ts`. Each fixture
case is `{name, config, doses, now, expected_state}`; both test
suites parametrize over it. Parity is enforced by tests, not by
code generation. This closes the open question in ADR-0004.

The TS helper exposes:
- `tickFrom(state: TimerStateOut, monotonicMs: number): TimerStateOut` —
  derives the visible state at a later monotonic-clock reading.
- `formatElapsed(seconds: number, locale?: string): string` —
  formats the count_up display string (with the `over 24h ago` cap
  per FR-003).
- `formatRemaining(seconds: number): string` — formats the count_down
  remaining time.
- `windowProgress(state: MultiSubDoseState): {used, total, expired_unused}` —
  compact accessor for the multi_sub_dose card.

**Rationale**: The math is small (≤ 6 functions, arithmetic + array
operations). Codegen would add tooling and a build step for marginal
gain. Shared JSON fixtures provide a true cross-language conformance
suite at near-zero cost. ADR-0004's "Negative" consequence ("two
implementations of the visible counter") is mitigated by the fixture
sharing — both implementations exercise the same expected-output
table.

**Alternatives considered**:
- *Declarative state-machine JSON description with a generator.*
  Rejected — over-engineered for ≤ 6 functions; would block ship on
  generator infrastructure.
- *Duplicate test files in each language.* Rejected — drift risk and
  maintenance overhead, exactly what the fixture sharing avoids.
- *Wasm-compile the Python module.* Rejected — adds a toolchain; the
  helper is small enough to hand-port.

---

## D5 — Window definition for `multi_sub_dose`

**Decision**: A window is a fixed-length time period
`[window_start, window_start + window_duration_minutes)`. The first
non-voided dose taken when no window is active becomes the
window-start dose; `window_start = d_first.taken_at`. All subsequent
non-voided doses falling inside `[window_start, window_end)` are
sub-doses of the same window. When `now >= window_end`, the window
is **expired**; the next dose taken starts a fresh window.

The "active window" returned in `TimerState.multi_sub_dose` is
computed by walking `doses` newest-first. We find the most recent
contiguous chain of doses that anchors a still-active window:
specifically, the most recent dose `d_recent` such that
`d_recent.taken_at + window_duration_minutes > now` defines a
candidate; we then identify the chain's start by walking backwards as
long as each successive dose falls inside `[earlier.taken_at,
earlier.taken_at + window_duration_minutes)` for the running
window-start. In practice, since the user's mental model is "tap
starts a window," the loop terminates quickly — at most
`times_per_day` iterations.

**Rationale**: Matches the user's clarify-session description ("when
they hit it it starts"). Pure function of `(med, doses, now)`. DST-
safe because all arithmetic is on UTC `datetime` values.

**Alternatives considered**:
- *Sliding window of last `window_duration_minutes`.* Rejected —
  doesn't match the user's "starts when they hit it" mental model;
  every dose would extend the window indefinitely.
- *Wall-clock buckets keyed to user timezone.* Rejected — DST-hostile
  and contradicts the user's agency framing (the app would impose
  bucket boundaries unrelated to when the user actually dosed).

---

## D6 — Error mapping infrastructure

**Decision**:
1. `MinIntervalNotElapsedError` is defined in `domain/timers.py` (a
   plain Python exception with `medication_id`, `next_allowed_at`,
   and `remaining_seconds` attributes — no Pydantic).
2. Wire-format model `MinIntervalViolation` lives in
   `backend/src/medminder/api/schemas/errors.py` (Pydantic).
3. A FastAPI exception handler registered in
   `backend/src/medminder/app.py` converts the domain error to a 409
   response with the `MinIntervalViolation` body.

**Rationale**: One place to map the domain error to HTTP — keeps
`api/doses.py` thin and prevents drift across handlers (`api/doses.py`
is the only handler that calls `create_dose()` today, but Phase 6
might add another).

**Alternatives considered**:
- *Catch the exception in each handler that calls `create_dose()`.*
  Rejected — duplication, drift risk.
- *Use FastAPI's `HTTPException` directly inside `create_dose()`.*
  Rejected — couples domain to FastAPI, violates Principle III.

---

## D7 — Test layout & coverage strategy

**Decision**: Test files (per the `plan.md` Project Structure):

| File | Scope | Notes |
|---|---|---|
| `backend/tests/domain/test_timers.py` | Pure-function | Parametrized over `fixtures/timer_cases.json`. No session fixture. Targets ≥ 95% line coverage on `domain/timers.py`. |
| `backend/tests/domain/test_timers_no_db_imports.py` | Principle III | After importing `domain.timers`, asserts neither `sqlalchemy` nor `fastapi` is in `sys.modules`. |
| `backend/tests/domain/test_doses_count_down_guard.py` | Domain integration | Uses async session fixture from `conftest.py`; mirrors `test_doses.py` style; covers happy path + guard rejection. |
| `backend/tests/api/test_doses_count_down_guard.py` | API integration | Hits `POST /api/doses` directly via `AsyncClient`; asserts 409 + exact body shape (FR-006). |
| `backend/tests/api/test_today_timer_state.py` | API integration | Verifies `TodayResponse.items[*].timer_state` for each mode + cross-user isolation (FR-014). |
| `backend/tests/api/test_medication_detail.py` | API integration | New endpoint; 200 happy path; 404 for other users' medications; 404 for soft-deleted. |
| `frontend/src/__tests__/timers.test.ts` | Pure-function | Parametrized over the same JSON fixture file. |
| `frontend/src/__tests__/CountUpDisplay.test.tsx` | Component | Renders strings; respects "over 24h ago" cap. |
| `frontend/src/__tests__/CountDownButton.test.tsx` | Component | Disabled while remaining > 0; calls take.mutate at zero; surfaces 409 body if API rejects. |
| `frontend/src/__tests__/MultiSubDoseCard.test.tsx` | Component | "Dose available" CTA logic; passive banner appears when previous window expired with unused slots; banner clears on new dose. |
| `frontend/e2e/timer-modes.spec.ts` | E2E | Playwright. SC-006 (count-down zero boundary; client and server agree). Quick Molly count-up smoke. Reuses `e2e/granny-smoke.spec.ts` login helper. |

**Rationale**: Honors FR-016 / SC-005 (project ≥ 85%, new domain
module ≥ 95%, no module below the constitution's 70% floor). The
shared JSON fixtures make the 95% target trivially reachable —
exhaustive case coverage of the math is one parametrize block.

**Alternatives considered**:
- *Skip frontend unit tests; rely on Playwright only.* Rejected —
  Playwright is slow and flaky for the 24h-cap formatting case;
  vitest + jsdom is the right tool.
- *Inline TS helper tests inside component tests.* Rejected — the
  helper is consumed by three components, so a separate test file
  prevents redundant coverage.
