# Implementation Plan: Phase 5 — Timer Modes

**Branch**: `2028-timer-modes` | **Date**: 2026-05-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-timer-modes/spec.md`

## Summary

Phase 5 introduces three timer modes (`count_up`, `count_down`,
`multi_sub_dose`) on top of Phase 4's mark-as-taken loop. The work
is one new pure-Python domain module (`domain/timers.py`), one new
API endpoint (`GET /api/v1/medications/{id}`), `timer_state` fields
added to `TodayItem` and `MedicationOut`, one new error class
(`MinIntervalNotElapsedError` mapped to HTTP 409), three frontend
display components plus a TypeScript counter helper, and three
Mermaid state diagrams. **No database schema changes** — Phase 1
already shipped `timer_preference`, `min_interval_minutes`, and
`window_duration_minutes` on `medications`. ADR-0004 graduates from
`Proposed` to `Accepted` with the User Story 1 PR.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 (strict), React 19, TanStack Router/Query, openapi-fetch — **no new runtime deps**
**Storage**: PostgreSQL 17 (existing schema; **no migrations in this phase**)
**Testing**: pytest + pytest-asyncio + httpx AsyncClient (backend, real Postgres via testcontainer fixture); vitest + Testing Library + jsdom (frontend); Playwright (E2E)
**Target Platform**: PWA — desktop Chrome / Firefox, iOS Safari, Android Chrome
**Project Type**: Web monorepo — `backend/` (FastAPI) + `frontend/` (Vite/React)
**Performance Goals**: Timer state visible within 2 seconds of opening the today view (SC-001); sub-dose progress updates within 1 second of dose mark (SC-003); count-up display matches wall-clock truth within 5s over 10 minutes (SC-001)
**Constraints**: Server-authoritative timer evaluation per ADR-0004 (no client decides whether a dose is allowed); event-driven client refetch only — **no periodic polling** (FR-009); UTC for all server arithmetic, user `timezone` honoured in display strings; constitution per-module 70% coverage floor preserved
**Scale/Scope**: Single-tenant per user; tens of medications per user; tens of doses per medication per day. No multi-tenant fan-out.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Compliance plan |
|---|---|---|
| **I — Security-Conscious by Default (NON-NEGOTIABLE)** | **PASS** | Cross-user isolation tests on every new endpoint (FR-014). New `GET /api/v1/medications/{id}` returns 404 (not 403) for other users' medications to avoid existence leaks. No new PII fields. No new third-party runtime deps. Threat-model note required in PR descriptions per principle. `checklists/security.md` is the merge gate for these. |
| **II — Fully Typed Across the Stack** | **PASS** | New domain module `domain/timers.py` and all new API code MUST satisfy `mypy --strict`. New TypeScript helper `frontend/src/lib/timers.ts` MUST satisfy `tsc --strict --noEmit`. OpenAPI is the single source of truth: `just generate-client` regenerates `frontend/src/api/v1.d.ts`; CI fails on drift. |
| **III — Loose Coupling, Testable Units** | **PASS** | `domain/timers.py` has no SQLAlchemy or FastAPI imports. Verified by an explicit `tests/domain/test_timers_no_db_imports.py` smoke test that imports the module and asserts neither `sqlalchemy` nor `fastapi` is in `sys.modules` after import. Pure functions are exhaustively tested via parametrized fixture cases. The `count_down` guard inside `domain/doses.py` reuses the same module. CLI does not need timer logic in this phase but the module is reusable. |
| **IV — Documented Decisions** | **PASS** | ADR-0004 graduates `Proposed → Accepted` alongside the US1 PR (FR-013). Three Mermaid state diagrams under `docs/diagrams/` (FR-012). Full spec-kit artifact set lands in `specs/005-timer-modes/`. Both `checklists/requirements.md` (already green) and `checklists/security.md` (new) ship with this phase. |
| **V — Cross-Platform Tooling Integrity** | **PASS** | No `.sh` / `.ps1` script pairs introduced. No `scripts/` changes. Dependency manifests (`backend/pyproject.toml`, `frontend/package.json`) unchanged. CI runs the existing pipeline (lint → typecheck → unit → integration → E2E → OpenAPI drift → build). The shared `timer_cases.json` fixture used by both pytest and vitest is **data**, not code, so it does not violate the "Python only under `scripts/`" rule. |

**No violations.** Complexity Tracking section below is empty.

## Project Structure

### Documentation (this feature)

```text
specs/005-timer-modes/
├── plan.md                       # This file
├── spec.md                       # Feature spec (from /speckit-specify + /speckit-clarify)
├── research.md                   # Phase 0 — design decisions D1–D7
├── data-model.md                 # Phase 1 — entities (existing + new)
├── quickstart.md                 # Phase 1 — per-story verification recipes
├── contracts/
│   └── timers.openapi.yaml       # Phase 1 — pre-implementation API contract
├── checklists/
│   ├── requirements.md           # Specify-stage merge gate (already green)
│   └── security.md               # New: Phase 5 security merge gate
└── tasks.md                      # Phase 2 output (created by /speckit-tasks; NOT here)
```

### Source Code (repository root)

```text
backend/
├── src/medminder/
│   ├── domain/
│   │   ├── timers.py             # NEW — pure-function timer state machine
│   │   ├── doses.py              # MODIFIED — count_down guard inside create_dose()
│   │   └── ... (passwords, medications, sessions — unchanged)
│   ├── api/
│   │   ├── medications.py        # MODIFIED — TimerState on list; new GET {id}
│   │   ├── doses.py              # MODIFIED — surfaces 409 from new error type
│   │   ├── schedules.py          # MODIFIED — TimerState on TodayItem
│   │   └── schemas/
│   │       ├── today.py          # MODIFIED — TodayItem.timer_state
│   │       ├── medications.py    # MODIFIED — MedicationOut.timer_state + MedicationDetailOut
│   │       ├── timers.py         # NEW — TimerStateOut wire model
│   │       └── errors.py         # NEW — MinIntervalViolation wire model
│   └── app.py                    # MODIFIED — register exception handler for MinIntervalNotElapsedError
└── tests/
    ├── domain/
    │   ├── test_timers.py                       # NEW — parametrized over fixtures/timer_cases.json
    │   ├── test_timers_no_db_imports.py         # NEW — Principle III enforcement
    │   ├── test_doses_count_down_guard.py       # NEW — guard in create_dose()
    │   └── fixtures/
    │       └── timer_cases.json                 # NEW — shared fixture (consumed by FE too)
    └── api/
        ├── test_doses_count_down_guard.py       # NEW — 409 + body via direct API
        ├── test_today_timer_state.py            # NEW — TimerState in today response
        └── test_medication_detail.py            # NEW — new endpoint + cross-user isolation

frontend/
├── src/
│   ├── lib/
│   │   ├── api.ts                # unchanged
│   │   └── timers.ts             # NEW — TS counter helper, hand-port of domain/timers.py
│   ├── api/v1.d.ts               # REGENERATED — adds timer_state, MinIntervalViolation, /medications/{id}
│   ├── hooks/
│   │   └── useMedicationDetail.ts # NEW — hook for the new endpoint
│   ├── components/
│   │   ├── timers/
│   │   │   ├── CountUpDisplay.tsx       # NEW — Molly's display
│   │   │   ├── CountDownButton.tsx      # NEW — Harry's button + ticking remaining time
│   │   │   └── MultiSubDoseCard.tsx     # NEW — Billy's window + "Dose available" + banner
│   │   └── TakenToggle.tsx       # MODIFIED — surfaces 409 body when count_down guard fires
│   ├── routes/
│   │   ├── today.tsx             # MODIFIED — renders timer components per item.timer_state.mode
│   │   ├── medications.index.tsx # MODIFIED — renders timer summary per row
│   │   └── medications.$medicationId.tsx # NEW — detail page hosting MultiSubDoseCard banner
│   └── __tests__/
│       ├── timers.test.ts                # NEW — vitest, parametrized over the same JSON fixture
│       ├── CountUpDisplay.test.tsx       # NEW
│       ├── CountDownButton.test.tsx      # NEW
│       └── MultiSubDoseCard.test.tsx     # NEW
└── e2e/
    └── timer-modes.spec.ts       # NEW — Playwright; SC-006 + Molly count-up smoke

docs/
├── adr/
│   └── 0004-timer-state-machines.md   # MODIFIED — Status: Proposed → Accepted (with US1 PR)
└── diagrams/
    ├── timer-count-up.md         # NEW — Mermaid state diagram
    ├── timer-count-down.md       # NEW — Mermaid state diagram
    └── timer-multi-sub-dose.md   # NEW — Mermaid state diagram
```

**Structure Decision**: Existing web-monorepo layout (`backend/` +
`frontend/`). Phase 5 follows the established conventions:
- Domain logic in `backend/src/medminder/domain/`.
- API schemas in `backend/src/medminder/api/schemas/`.
- Frontend components grouped by feature under
  `frontend/src/components/timers/`.
- Tests mirror the source tree under `backend/tests/{domain,api}/`
  and `frontend/src/__tests__/`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

(no entries — all gates passed)
