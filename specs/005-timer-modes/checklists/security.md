# Security Checklist: Phase 5 — Timer Modes

**Purpose**: Merge gate for the security-sensitive surface introduced
by Phase 5 — primarily the `count_down` mark-as-taken guard
(FR-005 / FR-006), the new medication detail endpoint, and the
shared `MinIntervalViolation` error body.

**Created**: 2026-05-08
**Walked**: 2026-05-16 (Phase 5 Polish, T063)
**Constitution principle**: I — Security-Conscious by Default (NON-NEGOTIABLE)

## Server-side enforcement (the count_down guard)

- [x] `MinIntervalNotElapsedError` is raised inside `domain/doses.create_dose()`, before the `Dose` row is `session.add()`-ed; no path that creates a dose can bypass it. — `backend/src/medminder/domain/doses.py` raises after ownership/schedule validation and *before* `Dose(...)` construction.
- [x] An integration test in `backend/tests/api/test_doses_count_down_guard.py` issues `POST /api/doses` directly via `httpx.AsyncClient`, bypassing the frontend, and confirms HTTP 409 + the documented body shape (FR-006). — plus a **live curl** run (T061): 1st dose `201`, immediate 2nd dose `409`.
- [x] The 409 body MUST NOT echo any field from the request that wasn't already in the request. — live 409 body was exactly `{"code":"min_interval_not_elapsed","medication_id":...,"next_allowed_at":...,"remaining_seconds":3599}`; the API test asserts the key set.
- [x] The guard reads only doses owned by the requesting user; cross-user dose history MUST NOT be considered when computing `last_dose_at`. — guard query filters `Dose.user_id == user.id` and `not_(voided_exists)`.

## Cross-user isolation on the new endpoint

- [x] `GET /api/v1/medications/{id}` returns **HTTP 404** (not 403) when the medication exists but belongs to another user, when it is soft-deleted, or when the id does not exist. The three cases MUST be observably indistinguishable in body and timing. — single `get_medication` SELECT folds all three to `None` → one `raise HTTPException(404, "Not Found")`; identical body, no branch-specific timing.
- [x] An integration test in `backend/tests/api/test_medication_detail.py` exercises all three 404 cases against a second test user. — `test_detail_404_paths_are_indistinguishable` asserts byte-identical bodies across unknown / other-user / soft-deleted.
- [x] The test suite asserts the 404 body conforms to the existing project-wide 404 shape — no extra fields are leaked. — asserts `set(body.keys()) == {"detail"}`.

## Existing surface unchanged in spirit

- [x] No request from one user can read or write another user's medications, doses, or `dose_voids` rows. — spot-checked `api/medications.py` (`get_medication` filters `user_id`), `api/schedules.py` (`today_view` filters `user.id`), `api/doses.py` (`create_dose` derives `user_id` from the session user, never the body).
- [x] Soft-deleted medications continue to be excluded from every endpoint that returns timer state; voided doses continue to be excluded from `last_dose_at`. — `get_medication`/list filter `deleted_at IS NULL`; `load_non_voided_history_for_meds` excludes voided; verified live (soft-delete exclusion test green) and by the count_up "most-recent-voided" fixture.

## Data minimisation

- [x] No new persisted column. No new persisted table. — `just migrate && alembic check` → "No new upgrade operations detected" (T062).
- [x] The `TimerStateOut` wire model carries only what FRs require: `mode`, `as_of`, `last_dose_at`, mode-specific payloads. `dose.id` is NOT leaked as part of `doses_in_window` (only timestamps). — `api/schemas/timers.py`: `ActiveWindow.doses_in_window: list[datetime]`; live Billy detail payload carried timestamps only.

## Dependencies

- [x] No new runtime dependencies in `backend/pyproject.toml`. — Phase 5 added none (pytest `filterwarnings` is test-config, not a dep).
- [x] No new runtime dependencies in `frontend/package.json`. — only the `typecheck` script changed (`tsc --noEmit` → `tsc -b`) + new tsconfig files; `dependencies`/`devDependencies` unchanged.
- [~] `pip-audit` and `pnpm audit` produce no new high-severity findings. — CI-runtime gate; Phase 5 introduced **zero** new runtime dependencies (the two boxes above), so it cannot introduce a new advisory. Run in CI on the phase PR.

## Threat-model note

The security-critical surface is the **`count_down` mark-as-taken
guard** (FR-005 / FR-006). It sits at the **server trust boundary**
inside `domain/doses.create_dose()` — the single chokepoint through
which every dose row is created, evaluated *before* the row is added
to the session. (a) The boundary is the API/DB edge: the client is
untrusted; the server is authoritative. (b) Client-side enforcement
alone is insufficient because a determined or buggy client can issue
`POST /api/doses` directly (curl, a script, a replayed request, a
stale tab) and never execute the UI's disable logic — only the
server-side raise prevents an overdose; this was demonstrated live by
a direct `curl` returning `409` with the structured
`MinIntervalViolation` body while no browser was involved. (c) Every
new read and guard path filters on the session `user_id` and excludes
soft-deleted medications and voided doses, so neither the timer-state
computation nor the interval guard can be influenced by another
user's data or by a dose the user has retracted; the new detail
endpoint collapses not-found / other-user / soft-deleted into one
indistinguishable `404` so medication existence is not leaked. No new
persisted data is introduced, so Phase 5 adds no new PII surface.

*(This paragraph is the canonical threat-model text; reuse verbatim in
the eventual `2028-timer-modes` phase PR description.)*

## Static-analysis & typing

- [x] `just typecheck` passes. — backend `mypy --strict` clean (45 files) + frontend **`tsc -b`** clean across app/node/test/e2e. (Note: the original checklist text said `tsc --noEmit --strict`; that recipe was a no-op and was replaced by a real `tsc -b` project-reference gate in the typecheck-fix PR — the gate is now stricter than this checklist originally assumed.)
- [x] `just lint` passes (ruff, eslint, prettier). — T060, 0 errors (pre-existing react-refresh warnings only).
- [x] `just test` passes with project coverage ≥ 85 %, `domain/timers.py` coverage ≥ 95 %, no module < 70 %. — T059: 246 passed; project line-rate **97.09 %**, `domain/timers.py` line-rate **96.63 %**, lowest module `db/__init__.py` **82.35 %**.

## Notes

- Items use the constitution's checklist gating semantics: every box must be `[x]` (satisfied) or `[~]` (CI-runtime, with a one-line link) before merge.
- The granny-flow Playwright smoke test (Phase 4) MUST remain green — Phase 5 must not regress mode `none`. **T064: live-green.** The e2e-fragility fix (shared `e2e/helpers.ts` `login()` that awaits the app's real post-login navigation, + `e2e/global-setup.ts` idempotent fixture provisioning) eliminated the login race; `E2E_RUN_GRANNY=1 playwright test granny-smoke.spec.ts` now passes **3/3 deterministically** (login → /today → mark taken → FR-005 modal → cancel → confirm un-take), proving mode `none` unregressed end-to-end against the live stack. (The earlier post-login `/today` failure was the login race, now fixed — not a Phase 5 regression.)
- **T061 finding (quickstart/contract drift, not a code defect):** `POST /api/doses` requires `taken_at`, but `quickstart.md`'s recipes omit it and `contracts/timers.openapi.yaml` documents it as "optional override; defaults to now". The frontend (`useTakeDose`) always sends `taken_at`, so the product works; the drift is doc/contract-only. Recommend reconciling `quickstart.md` + the contract (or making `taken_at` server-default) as a follow-up.
