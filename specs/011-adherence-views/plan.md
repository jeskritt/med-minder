# Implementation Plan: Long-term adherence views

**Branch**: `011-adherence-views` | **Date**: 2026-05-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-adherence-views/spec.md`

## Summary

Give long-running users a glance answer to "did I take it yesterday / last week?" plus
course progress for fixed-course meds, a trend view, and a CSV export — **all derived
from existing data** (`doses`, `dose_voids`, `medications`, `schedules`,
`schedule_medications`), with **no schema change**. The work is a new read-only domain
module `domain/adherence.py` that generalizes the existing per-day "scheduled slot ×
effective dose" logic (today's `today_view`) across a **date range**, bucketing into the
user's current IANA zone and classifying each day per medication as
**taken / partial / missed / future / inactive**. A scheduled slot is "missed" only once
its scheduled time + a fixed **4-hour tolerance** has passed with no non-voided dose;
unlike `today_view`, adherence **honors `schedules.days_of_week`** (a Mon–Fri med is not
"missed" on Saturday). The module also computes a per-window **adherence percentage**
(taken ÷ expected scheduled doses, excluding inactive and future days) and **course
progress** (non-voided dose count vs `medications.total_doses`, with a completion flag —
display-only, no side effects).

A new `/api/v1/adherence` router exposes two endpoints: a per-medication windowed
adherence read (feeding both the calendar and the stacked-bar trend from one payload) and
a CSV export of the user's full dose history (one row per non-voided dose; soft-deleted
meds marked "(removed)"). The frontend adds an adherence section to the medication detail
route (calendar ⇄ trend toggle, month/window navigation, percentage, course progress) and
an Export action on the medications list. Every per-day status carries a non-color icon
signal (check / dash / cross) alongside color, so the views don't rely on color alone.
Closes with **ADR-0016** (adherence is derived, never stored; missed semantics + 4h
tolerance; current-TZ bucketing; voids excluded) and a doc sweep (glossary, the
adherence-tracking design doc's open questions, ER "no change" note, `CLAUDE.md`).

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5 + React 19 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (typed `Mapped`), Pydantic v2 strict,
stdlib `zoneinfo` + `csv` (no new dependency); TanStack Router/Query, `openapi-fetch` with
the generated `api/v1.d.ts` client. CSV is built with the stdlib `csv` module and returned
via a FastAPI `StreamingResponse` (`text/csv`, `Content-Disposition: attachment`).

**Storage**: PostgreSQL — **read-only** over existing `doses`, `dose_voids`,
`medications`, `schedules`, `schedule_medications`. **No new table, no migration.**

**Testing**: pytest + pytest-asyncio + httpx `ASGITransport` against **real Postgres**
(rollback-per-test, prepared-statement cache disabled); vitest + Testing Library (frontend).

**Target Platform**: Linux server + browser PWA.

**Project Type**: Web application (backend + frontend).

**Performance Goals**: Standard interactive web. A user can answer "did I take it on a
given past day?" in under 10 seconds from opening the app (SC-001); a month of per-day
statuses for one medication returns well within a normal interactive page load.

**Constraints**: `mypy --strict` and `tsc --noEmit` strict; coverage ≥ 85% (no module
< 70%); own-data-only by construction (every query scoped to `get_current_user`, FR-015);
no new PII fields (data minimization, Principle I); the CSV carries PHI so it is served
only to the authenticated owner and never cached (the PWA service worker already denylists
`/api` from caching — ADR-0015).

**Scale/Scope**: Single-tenant, modest dose volume. Net new surface: **0 dependencies,
0 tables, 0 migrations**; 2 endpoints (windowed adherence read + CSV export); 1 new domain
module (+1 generalized query path); ~4 React components, 1 lib hook module, edits to the
medication-detail route and the medications-list header.

*No `NEEDS CLARIFICATION` remain — the `/speckit-clarify` answers (skipped→missed; numeric
adherence % is a deliverable; course-completion is display-only) and the documented
Assumptions (4h tolerance, current-TZ bucketing, voids excluded, derived-not-stored) are
settled in `spec.md`.*

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — still PASS.*

- **I. Security-Conscious by Default (NON-NEGOTIABLE)** — PASS. Both endpoints sit behind
  `get_current_user`; every query is scoped to the session user's own medications and doses
  (no cross-user access, FR-015) — no medication_id from the path is trusted without an
  ownership filter. **No new data field is collected** (adherence is derived), satisfying
  data minimization. The CSV export contains medication names and dose timestamps (PHI): it
  is returned only to the authenticated owner, is not logged, and is not cached by the
  service worker (`/api` is already denylisted, ADR-0015). New surface area (2 read
  endpoints) gets its threat note in **ADR-0016** and the PR "Security considerations"
  section. No new dependency → no new audit surface.
- **II. Fully Typed Across the Stack** — PASS. New Pydantic response models run strict
  (`extra="forbid"`); the new domain dataclasses are fully annotated; the TS client is
  **regenerated** (`just generate-client`), never hand-edited; `mypy --strict` + `tsc
  --noEmit` cover new code. CSV rows are assembled from typed domain objects.
- **III. Loose Coupling, Testable Units** — PASS. All classification (day status, tolerance,
  percentage, course progress) lives in `domain/adherence.py` and is testable without HTTP.
  The pure date/status math is separated from the DB-loading orchestration (mirroring how
  `domain/timezone.py` is split from `today_view`). The endpoints are thin transport. No
  logic is duplicated — the per-day "scheduled slot × effective dose" shape reuses the same
  `not_(voided_exists)` and `resolve_today_bounds` building blocks `today_view` uses.
- **IV. Documented Decisions** — PASS with deliverables: **ADR-0016** (adherence derived,
  never stored; "missed" = scheduled-and-untaken past a 4h tolerance, honoring
  `days_of_week`; current-TZ bucketing; voids excluded; course-completion display-only) — the
  next free ADR number after 0015. **No ER change** (no schema delta) — the ER diagram gets a
  one-line "Phase 9 adds no tables (adherence derived)" note rather than a structural edit.
  **No new sequence/state diagram is warranted**: this is a read-only reporting view — it adds
  no new user flow with side effects and no new state machine — so Principle IV's diagram
  obligation is satisfied by the ER note plus the `docs/design/adherence-tracking.md` update.
  The `docs/design/adherence-tracking.md` "Open questions" (voids, time zone) are resolved.
  `checklists/requirements.md` exists; this read-only, no-new-data feature does not warrant a
  separate `security.md` (no new write surface, no new field, no new dependency) — the threat
  note lives in ADR-0016 and the PR.
- **V. Cross-Platform Tooling Integrity** — PASS. **No migration, no `scripts/` change, no
  new dependency** (stdlib `csv`/`zoneinfo`). `just generate-client` is the only generator
  invoked. CSV is generated server-side in the Linux container; no `.sh`/`.ps1` added.

No violations → **Complexity Tracking is empty / omitted.**

## Project Structure

### Documentation (this feature)

```text
specs/011-adherence-views/
├── plan.md              # This file
├── research.md          # Phase 0 — design decisions (D1–D8)
├── data-model.md        # Phase 1 — derived views over existing tables (no schema change)
├── quickstart.md        # Phase 1 — manual + API + automated verification
├── contracts/
│   └── adherence.openapi.yaml   # Phase 1 — /api/v1/adherence read + CSV export
├── checklists/
│   └── requirements.md  # spec-quality gate (exists)
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/src/medminder/
├── api/
│   ├── adherence.py        # NEW: /api/v1/adherence router —
│   │                       #   GET /medications/{id}  (windowed per-day statuses + % + course)
│   │                       #   GET /export.csv         (full non-voided dose history)
│   │                       #   + Pydantic response schemas (extra="forbid")
│   └── app.py              # MODIFY: include_router(adherence.router)
├── domain/
│   └── adherence.py        # NEW: pure day-status classification (taken/partial/missed/
│                           #   future/inactive, 4h tolerance, days_of_week honored) +
│                           #   window % + course progress; DB orchestration to load
│                           #   scheduled slots × non-voided doses across a date range and
│                           #   bucket into the user's current TZ. Reuses resolve_today_bounds
│                           #   and the not_(voided_exists) pattern.

backend/tests/
├── domain/
│   └── test_adherence.py            # NEW: classification matrix (taken/partial/missed/
│                                    #   future/inactive), 4h tolerance, days_of_week,
│                                    #   PRN never-missed, void exclusion, TZ bucketing,
│                                    #   course progress + completion, % excludes inactive/future
└── api/
    ├── test_adherence_api.py        # NEW: 401 anon; own-data-only (404/empty for others' meds);
    │                                #   date-range honored; % present for scheduled, absent PRN
    └── test_adherence_export.py     # NEW: CSV columns + order; soft-deleted "(removed)";
                                     #   voided excluded; text/csv + attachment headers; own-data-only

frontend/src/
├── routes/
│   └── medications.$medicationId.tsx   # MODIFY: embed <AdherenceView> (calendar/trend + course)
├── components/
│   ├── adherence/
│   │   ├── AdherenceView.tsx        # NEW: calendar⇄trend toggle, month/window nav, % readout
│   │   ├── AdherenceCalendar.tsx    # NEW: month grid; color + check/dash/cross icon per day
│   │   ├── AdherenceTrend.tsx       # NEW: per-day stacked bars over week/month window
│   │   └── CourseProgress.tsx       # NEW: "N of M" + course-complete state (display-only)
│   └── medications/                 # MODIFY: add an Export (CSV) action to the list header
├── lib/
│   └── adherence.ts                 # NEW: React-Query hook for the adherence read +
│                                    #   CSV-download helper (fetch blob → anchor click)
├── api/v1.d.ts                      # REGENERATE via `just generate-client`
└── __tests__/
    ├── AdherenceCalendar.test.tsx   # NEW: day cells render correct state + non-color icon
    ├── AdherenceTrend.test.tsx      # NEW: bar segments reflect taken/missed
    └── CourseProgress.test.tsx      # NEW: "9 of 14" + complete state; hidden when no course

docs/
├── adr/0016-adherence-derivation.md   # NEW (doc sweep) — next free number is 0016
├── design/adherence-tracking.md        # MODIFY: resolve the "Open questions" (voids, TZ)
├── diagrams/er.md                      # MODIFY: one-line "Phase 9 adds no tables" note
├── glossary.md                         # MODIFY: "adherence %", "missed", "course complete"
└── user_stories.md                     # MODIFY: confirm/refine UC-6 against shipped behavior

CLAUDE.md                  # MODIFY: SPECKIT marker → this plan; add a "surprises" note (doc sweep)
```

**Structure Decision**: Existing web layout (`backend/` + `frontend/`). The backend change
is a single new read-only domain module plus a thin `/api/v1/adherence` router — no models,
no migration. The per-day adherence computation is a generalization of the existing
`today_view` shape across a date range, kept pure-where-possible so the classification matrix
is unit-testable without a DB. The frontend embeds the adherence section in the existing
medication-detail route (avoiding a new route layout) and reuses the `mm-*` design-system
classes/tokens for the calendar/trend coloring, with an explicit non-color icon on every cell.
ADR/glossary/design-doc/ER edits are the doc-sweep tasks executed in the implement phase.
