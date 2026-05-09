# Security Checklist: Phase 5 — Timer Modes

**Purpose**: Merge gate for the security-sensitive surface introduced
by Phase 5 — primarily the `count_down` mark-as-taken guard
(FR-005 / FR-006), the new medication detail endpoint, and the
shared `MinIntervalViolation` error body.

**Created**: 2026-05-08
**Constitution principle**: I — Security-Conscious by Default (NON-NEGOTIABLE)

## Server-side enforcement (the count_down guard)

- [ ] `MinIntervalNotElapsedError` is raised inside `domain/doses.create_dose()`, before the `Dose` row is `session.add()`-ed; no path that creates a dose can bypass it.
- [ ] An integration test in `backend/tests/api/test_doses_count_down_guard.py` issues `POST /api/doses` directly via `httpx.AsyncClient`, bypassing the frontend, and confirms HTTP 409 + the documented body shape (FR-006).
- [ ] The 409 body MUST NOT echo any field from the request that wasn't already in the request (no token leakage, no other-medication leakage).
- [ ] The guard reads only doses owned by the requesting user; cross-user dose history MUST NOT be considered when computing `last_dose_at`.

## Cross-user isolation on the new endpoint

- [ ] `GET /api/v1/medications/{id}` returns **HTTP 404** (not 403) when the medication exists but belongs to another user, when it is soft-deleted, or when the id does not exist. The three cases MUST be observably indistinguishable in body and timing.
- [ ] An integration test in `backend/tests/api/test_medication_detail.py` exercises all three 404 cases against a second test user.
- [ ] The test suite asserts the 404 body conforms to the existing project-wide 404 shape — no extra fields are leaked.

## Existing surface unchanged in spirit

- [ ] No request from one user can read or write another user's medications, doses, or `dose_voids` rows. Spot-check the modified handlers (`api/medications.py`, `api/schedules.py`, `api/doses.py`) for filter clauses on `user_id`.
- [ ] Soft-deleted medications continue to be excluded from every endpoint that returns timer state; voided doses continue to be excluded from `last_dose_at`.

## Data minimisation

- [ ] No new persisted column. No new persisted table. (Phase 5 adds zero PII surface.)
- [ ] The `TimerStateOut` wire model carries only what FRs require: `mode`, `as_of`, `last_dose_at`, mode-specific payloads. Confirm `dose.id` is NOT leaked as part of `doses_in_window` (only timestamps are).

## Dependencies

- [ ] No new runtime dependencies in `backend/pyproject.toml`.
- [ ] No new runtime dependencies in `frontend/package.json`.
- [ ] `pip-audit` and `pnpm audit` produce no new high-severity findings on the PR (constitution Principle V).

## Threat-model note

- [ ] PR description includes a one-paragraph threat-model note covering: (a) what trust boundary the count_down guard sits at, (b) why client-side enforcement alone would be insufficient, (c) the soft-delete + voided-dose filter behavior on every new code path.

## Static-analysis & typing

- [ ] `just typecheck` passes (`mypy --strict` and `tsc --noEmit --strict`).
- [ ] `just lint` passes (ruff, eslint, prettier).
- [ ] `just test` passes with project coverage ≥ 85 %, `domain/timers.py` coverage ≥ 95 %, no module < 70 %.

## Notes

- Items use the constitution's checklist gating semantics: every box must be `[x]` (satisfied) or `[~]` (CI-runtime, with a one-line link) before merge.
- The granny-flow Playwright smoke test (Phase 4) MUST remain green — Phase 5 must not regress mode `none`.
