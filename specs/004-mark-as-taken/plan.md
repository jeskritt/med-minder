# Implementation Plan: mark-as-taken

**Branch**: `004-mark-as-taken` | **Date**: 2026-05-07 | **Spec**: [004-mark-as-taken/spec.md](spec.md)
**Input**: Feature specification from `/specs/004-mark-as-taken/spec.md`

## Summary

Phase 4 turns the Phase 1a schema into a working "did I take it, and
when?" loop. The `doses` table already exists with the columns this
phase needs (`user_id`, `medication_id`, `schedule_id`, `taken_at`,
`quantity`); Phase 4 adds **only** a new `dose_voids` table to record
un-take events as compensating rows, honoring D6's append-only
invariant. We expose `POST /api/doses`,
`POST /api/doses/{id}/void`, and `GET /api/schedules/today`, build the
Today view in the frontend with optimistic-update semantics on the
"Taken" toggle, and land the repo's first Playwright smoke covering
the Granny flow end-to-end.

## Technical Context

**Language/Version**: Python 3.12+ (Backend), TypeScript strict / Node 20+ (Frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic, Alembic (Backend); React 18, Vite, TanStack Query, TanStack Router, shadcn/ui (Frontend)
**Storage**: PostgreSQL 16 — existing `doses` table from Phase 1a; new `dose_voids` table this phase.
**Testing**: pytest with `pytest-cov` (Backend, ≥85% gate), Vitest (Frontend unit), Playwright/Chromium (Frontend E2E smoke — first in repo).
**Target Platform**: Web (Vercel/Cloudflare Pages frontend, Koyeb backend).
**Project Type**: Web Application (existing `backend/` + `frontend/` split).
**Performance Goals**: Optimistic UI feedback on the "Taken" toggle (sub-100ms perceived latency); Today view query indexed on `(user_id, taken_at)` and the `(schedule_id, medication_id)` join keys.
**Constraints**:
- `doses` is append-only; corrections via `dose_voids` (Phase 1a D6).
- All write `user_id`s derived from session, never request body.
- Cross-user access returns `403`.
- Per FR-008, optimistic UI with rollback + toast on failure.
**Scale/Scope**: Phase 4 scope only — Today view + Doses create/void + smoke E2E. Adherence dashboards are Phase 9; cooldown/interaction enforcement is Phase 6; reminders/Push are Phase 7.

### Resolved clarifications

The earlier draft of this plan flagged three `NEEDS CLARIFICATION`
items. They are resolved in `research.md` and summarized here:

1. **Optimistic UI** — TanStack Query `useMutation` with
   `onMutate` / `onError` / `onSettled`. Snapshot the Today query
   cache, write the optimistic update, restore on error with a toast,
   invalidate on settle. (`research.md` §"Optimistic UI updates".)
2. **Timezone-aware Today** — Backend computes
   `[start_utc, end_utc)` and the day-of-week bit using `zoneinfo`
   from the user's `timezone` (or a `?timezone=` override). SQL
   filters on `doses.taken_at` and the `schedules.days_of_week`
   bitmask. (`research.md` §"Timezone-aware Today bounds".)
3. **Playwright config** — `@playwright/test` added to the
   `frontend/` package, `playwright.config.ts` orchestrates `pnpm dev`
   and Compose's `backend` service via `webServer`. CI runs Chromium
   only this phase. (`research.md` §"Playwright smoke configuration".)

## Phase 1 alignment — what we are *not* changing

Five Phase 1a decisions constrain this phase. They are upheld, not
revisited:

- **D4** — `doses.user_id` is denormalized; the Postgres trigger
  enforcing `doses.user_id == medications.user_id` is already in
  place. Service layer derives `user_id` from the session.
- **D6** — `doses` are append-only; never `UPDATE` or `DELETE`. Undo
  flows through `dose_voids`.
- **D7** — `quantity` is `NUMERIC(10, 3) CHECK > 0`. We default to
  `medications.quantity_per_dose` when omitted but never bypass the
  check.
- **D11** — `taken_at` is `TIMESTAMPTZ`; schedule `time_of_day` is
  naive in user-local time. Today bounds are computed in the user's
  IANA zone.
- **`schedule_id` linkage** — Phase 1a added a nullable
  `doses.schedule_id` for exactly this purpose. The Today view sends
  it back on `POST /api/doses`; ad-hoc doses leave it `NULL`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- **I. Security-Conscious by Default** — Yes. All endpoints require an
  authenticated session; `user_id` is derived server-side; cross-user
  access returns `403`. The Postgres trigger from Phase 1a remains the
  belt-and-suspenders backstop. Threat-model notes go in the PR.
- **II. Fully Typed Across the Stack** — Yes. New SQLAlchemy model
  for `dose_voids` uses `Mapped[...]`. Pydantic schemas define request
  / response shapes. OpenAPI client is regenerated; the frontend
  consumes the typed client only.
- **III. Loose Coupling, Testable Units** — Yes. Domain logic (dose
  insert, dose void, today-view query) lives in
  `backend/src/medminder/domain/doses.py` and is unit-tested against
  the Postgres service container. The HTTP layer is a thin adapter.
- **IV. Documented Decisions** — Yes. Phase spec, plan, research,
  data-model, contracts, and quickstart are committed under
  `specs/004-mark-as-taken/`. ER diagram updated to show
  `dose_voids`. ADR is written only if a non-obvious decision lands
  (e.g., the void-table design is the candidate; if not promoted to
  an ADR, the rationale stays in `research.md`).
- **V. Cross-Platform Tooling Integrity** — Yes. Playwright smoke is
  added to the CI gate without `continue-on-error`. Any helper
  scripts are Python under `scripts/` (per project memory: no
  `.sh`/`.ps1` pairs).

## Project Structure

### Documentation (this feature)

```text
specs/004-mark-as-taken/
├── plan.md              # this file
├── spec.md              # feature spec with clarifications
├── research.md          # Phase 0 — decisions and alternatives
├── data-model.md        # existing doses (referenced) + new dose_voids
├── quickstart.md        # dev setup and manual verification flow
├── contracts/api.md     # endpoint contracts
├── checklists/
│   └── requirements.md  # spec-quality checklist
└── tasks.md             # generated by /speckit-tasks (not by /speckit-plan)
```

### Source Code (repository root, additions only)

```text
backend/
├── src/medminder/
│   ├── db/models/
│   │   └── dose_voids.py        # NEW
│   ├── domain/
│   │   └── doses.py             # NEW — create_dose, void_dose, today_view
│   ├── api/
│   │   └── doses.py             # NEW — FastAPI router
│   └── api/schedules.py         # NEW endpoint: GET /api/schedules/today
├── alembic/versions/
│   └── XXXX_add_dose_voids_table.py   # NEW migration
└── tests/
    ├── db/test_dose_voids.py    # NEW — constraint coverage
    ├── domain/test_doses.py     # NEW — service rules and today-view logic
    └── api/test_doses.py        # NEW — endpoint contract tests

frontend/
├── src/
│   ├── routes/today.tsx         # NEW Today route (TanStack Router)
│   ├── components/TakenToggle.tsx
│   ├── components/UntakeConfirmModal.tsx
│   └── hooks/useToday.ts        # TanStack Query
├── tests/                        # Vitest
│   └── TakenToggle.test.tsx     # rollback-on-error coverage
├── e2e/
│   └── granny-smoke.spec.ts     # NEW — Playwright smoke
└── playwright.config.ts         # NEW
```

**Structure Decision**: Existing Option-2 split (backend + frontend),
no new top-level dirs.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified.

*No violations.* The single design choice that warranted scrutiny —
"how to model un-take given `doses` is append-only" — is resolved by
the new `dose_voids` table per Phase 1a D6, with rationale captured in
`research.md`.
