# Phase 0: Research

## Phase 1 alignment — the `doses` table already exists

- **Decision**: Phase 4 ships **no migration to `doses`**. We use the
  table as defined in
  `specs/2026-04-29-phase-1-data-model/requirements.md` §"doses"
  (columns `id, user_id, medication_id, schedule_id, taken_at,
  quantity, created_at`; trigger enforcing
  `doses.user_id == medications.user_id`; append-only per D6).
- **Rationale**: An earlier draft of this phase proposed a fresh
  `doses` table with only `(id, medication_id, taken_at, created_at,
  updated_at)`. That conflicted with five Phase 1a decisions (D4,
  D6, D7, the schedule-slot linkage, and the no-`updated_at`
  invariant). The schema we already migrated covers this phase's needs
  without change.
- **Alternatives considered**: Adding columns to `doses` for void
  state — rejected because D6 explicitly forbids mutating dose rows.

## Undo via compensating row, not `DELETE`

- **Decision**: A new `dose_voids` table (`dose_id UNIQUE → doses.id`,
  `voided_by_user_id`, `voided_at`, `created_at`). Un-taking is
  `POST /api/doses/{id}/void`, which inserts a row. Readers
  (Today view, adherence) join `LEFT JOIN dose_voids` and filter to
  rows where no void exists.
- **Rationale**: D6 plus the constitutional "Append-only audit trail"
  rule prohibit `UPDATE` and `DELETE` on `doses`. A separate void
  table is the cleanest expression of "compensating row" — it
  preserves the original `taken_at`, attributes the void to a user, and
  makes double-void detection a `UNIQUE` constraint. The honest
  adherence record the mission promises survives a misclick.
- **Alternatives considered**:
  - `voided_at` column on `doses` — rejected; that *updates* the dose
    row, breaking the immutability rule.
  - Insert a "negative quantity" compensating row in `doses` itself —
    rejected; conflicts with the existing
    `CHECK (quantity > 0)` (D7) and muddies adherence math.
  - Hard `DELETE` of the dose — rejected; loses audit history and
    cannot answer "did you intend this taken at one point?".

## Today-view slot identity

- **Decision**: The Today view is keyed by the
  `(schedule_id, medication_id)` pair, not by `medication_id` alone. A
  medication on two schedules that both fire today appears as two
  rows. `POST /api/doses` carries the slot's `schedule_id` so each
  slot's "taken" state is tracked independently.
- **Rationale**: `medications.times_per_day` can be > 1 (D1), and a
  single medication can be attached to multiple schedules through
  `schedule_medications` (M:M). Without a per-slot key the UI cannot
  distinguish "morning Lisinopril taken, evening still pending" from
  "Lisinopril taken." `doses.schedule_id` was added in Phase 1a
  precisely for this; we use it.

## `quantity` defaulting on `POST /api/doses`

- **Decision**: `quantity` is optional on the dose-create request.
  When omitted, the service substitutes
  `medications.quantity_per_dose`. `schedule_id` carries no implicit
  quantity override.
- **Rationale**: The Granny flow is one-tap: she clicks "Taken" with
  no quantity input. Defaulting from the medication keeps the typical
  case zero-friction while preserving the freedom to log a partial
  dose explicitly (Billy's split-dose case from `docs/user_stories.md`).
- **Alternatives considered**: Require `quantity` always — rejected;
  forces the UI to send a value the server already knows.

## Optimistic UI updates with TanStack Query

- **Decision**: Use `useMutation`'s `onMutate` / `onError` /
  `onSettled` lifecycle. `onMutate` cancels in-flight refetches of the
  Today query, snapshots the cache, and writes the optimistic update.
  `onError` restores the snapshot and emits a toast. `onSettled`
  invalidates the Today query so the next read reconciles with the
  server.
- **Rationale**: This is the TanStack Query-recommended pattern. It
  keeps the cache as the single UI source of truth, which avoids the
  "two states, one screen" bugs that arise when optimistic state lives
  in component-local React state.
- **Alternatives considered**: Component-local optimistic state —
  rejected for the divergence reason above. Pessimistic UI (wait for
  the server) — rejected because FR-008 requires optimistic feedback.

## Timezone-aware "Today" bounds

- **Decision**: The backend computes `[start_utc, end_utc)` for the
  target date in the user's timezone (or the `timezone` query
  parameter when supplied) using Python's `zoneinfo`, then queries
  `doses` with `taken_at >= start_utc AND taken_at < end_utc`. The
  day-of-week bit for the `schedules.days_of_week` mask is also
  computed in the same zone.
- **Rationale**: Schedule `time_of_day` is stored naive in user-local
  time (D11); `doses.taken_at` is `TIMESTAMPTZ`. Computing both bounds
  in one place server-side keeps the SQL straightforward and indexable
  on `(user_id, taken_at)`.
- **Alternatives considered**: Send all medications/doses to the
  client and filter there — rejected; payload grows linearly with
  history and the server-side filter is simple.

## Playwright smoke configuration

- **Decision**: Add `@playwright/test` to the `frontend/` package.
  `playwright.config.ts` runs against `pnpm dev` (frontend) and the
  Docker Compose `backend` service via a `webServer` block.
  CI runs the smoke on Chromium only (Phase 10 broadens the matrix per
  the roadmap).
- **Rationale**: Playwright is the standard for Vite/React E2E and
  has the cleanest server-orchestration story. The smoke covers the
  Granny flow per FR-006: log in → add a medication and schedule →
  open Today → mark taken → verify the row is greyed out.
- **Alternatives considered**: Cypress — rejected, slower in CI and
  weaker parallelism. Selenium-via-Python — rejected; the test
  exercises a frontend flow, so it should live with the frontend.
