# Implementation Plan: Phase 7 — Reminders + Snooze

**Branch**: `008-reminders-snooze` | **Date**: 2026-05-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-reminders-snooze/spec.md`

## Summary

Phase 7 brings the dormant `reminders` and `push_subscriptions` tables (shipped Phase 1)
to life: an **in-process APScheduler** dispatch tick generates and fires dose reminders per
schedule slot, delivers them via **Web Push (VAPID)**, supports a fixed **one-hour snooze**,
defers around per-user **quiet hours**, keeps reminders in step with **schedule mutations**,
and turns `refill_count` into a **live, decrementing supply count** that raises an opt-in
**refill warning** at `refill_threshold`. Reminders are also readable, snoozeable, and
dismissable **in-app** (push is best-effort). Taking a dose **auto-resolves** the slot's
pending reminder; misfires during downtime fire **once within a bounded grace window** and
otherwise stay overdue in-app.

The durable state is the Alembic-managed `reminders` table — **not** APScheduler's own job
store (research **D1** refines ADR-0002; the dual DML-only runtime role can't run the
jobstore's DDL). The scheduler runs a single recurring **dispatch tick** that scans the
table. The work is: two new backend domain modules (a **pure** `domain/reminders.py` for
fire-time / quiet-hours / grace / threshold math, and an async `domain/reminder_dispatch.py`
orchestrating generate/dispatch/snooze/dismiss/resolve/refill), a `domain/push.py` Web-Push
sender, a top-level `scheduler.py` wired into the app lifespan, refill + resolution hooks in
`domain/doses.py` / `domain/medications.py`, reminder (re)generation hooks in the schedules
and medications routers, two new routers (`api/push.py`, `api/reminders.py`), one Alembic
revision adding **indexes + a partial-unique refill-dedup constraint** (no new tables/columns),
a minimal frontend (service worker, enable-notifications control, in-app reminders list with
snooze/dismiss), two new pinned runtime deps (`apscheduler`, `pywebpush`) + VAPID settings, a
new `scripts/generate_vapid_keys.py`, a Mermaid state + sequence diagram, the doc sweep
(glossary/UC-5.4 `doses_remaining → refill_count`), and the promotion of **ADR-0002
`Proposed → Accepted`** with the refined approach documented.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 (strict), React 19, TanStack Router/Query, openapi-fetch — **two NEW pinned runtime deps**: `apscheduler>=3.11,<4.0` (in-process `AsyncIOScheduler`), `pywebpush>=2.0,<3.0` (Web Push + bundled `py-vapid`)
**Storage**: PostgreSQL 17 — **one Alembic revision** adding indexes + a partial-unique refill-dedup index on the existing `reminders` table; **no new tables or columns**
**Testing**: pytest + pytest-asyncio + httpx `AsyncClient`/`ASGITransport` (backend, real Postgres via the rollback fixture); vitest + Testing Library + jsdom (frontend); Playwright (E2E, skip-gated)
**Target Platform**: PWA — desktop Chrome / Firefox, Android Chrome, iOS Safari 16.4+ (Web Push)
**Project Type**: Web monorepo — `backend/` (FastAPI) + `frontend/` (Vite/React)
**Performance Goals**: dose reminders fire within one tick interval (≤60s) of their slot; snoozed reminder re-fires within ±1 min (SC-003); dispatch tick stays well under the interval at single-tenant volume
**Constraints**: server-authoritative scheduling (a manipulated client clock cannot make a reminder fire/skip); **single app instance** (ADR-0002) — the scheduler must run exactly once; push delivery best-effort & non-blocking to the tick; VAPID private key and raw subscription secrets are env/secret-only, never logged or returned (FR-002/FR-017); UTC arithmetic with the user's `timezone` for local fire times and quiet-hours wrap; coverage ≥85% with the per-module 70% floor; `alembic check` stays green
**Scale/Scope**: single-tenant per user; tens of meds, a handful of schedules, a few dozen reminders/day; no multi-tenant fan-out

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Compliance plan |
|---|---|---|
| **I — Security-Conscious by Default (NON-NEGOTIABLE)** | **PASS** | All subscription/reminder/snooze/dismiss operations are scoped to the logged-in user; a cross-user negative test proves no reminder/subscription leaks or mutations (FR-017, SC-008). The **VAPID private key** lives only in settings/secrets and is never sent to the client, logged, or returned; only the **public** key is exposed (FR-002, SC-009). Push subscription `endpoint`/`p256dh`/`auth` are existing minimised fields (no new PII). New surface (two routers, the push sender, the scheduler tick) gets a "Security considerations" PR section. A `checklists/security.md` merge gate is added alongside the existing `checklists/requirements.md`. |
| **II — Fully Typed Across the Stack** | **PASS** | New `domain/reminders.py` (pure), `domain/reminder_dispatch.py`, `domain/push.py`, `scheduler.py`, schemas and the two routers satisfy `mypy --strict`; new `Index` objects keep the `Reminder` model SQLAlchemy-2.0 typed; Pydantic strict. New TS (push lib, hooks, reminders route, SW types) satisfies `tsc --noEmit` strict. OpenAPI is the single source of truth: `just generate-client` regenerates `frontend/src/api/v1.d.ts`; CI fails on drift. `pywebpush` has no stubs → a single scoped `# type: ignore[import-untyped]` with rationale at its import site (isolated in `domain/push.py`). |
| **III — Loose Coupling, Testable Units** | **PASS** | `domain/reminders.py` holds the fire-time / quiet-hours-wrap / grace / threshold-crossing math with **no SQLAlchemy/FastAPI/APScheduler imports** — enforced by `tests/domain/test_reminders_no_db_imports.py` (mirrors the Phase 5/6 analogue) and exhaustively unit-tested. The async orchestration (`reminder_dispatch.py`) calls that one pure module; the scheduler tick, the API endpoints, and the dose write-path hooks all call the *same* orchestration functions — no duplicated logic across transports. The push sender is injected into the dispatcher (a `send` callable), so dispatch is testable with a fake sender and no network. |
| **IV — Documented Decisions** | **PASS** | **ADR-0002 graduates `Proposed → Accepted`** (FR-020), documenting the refined approach (reminders-table-as-truth + recurring tick; default in-memory job store; why not `SQLAlchemyJobStore` — the DML-only runtime role). The **reminder lifecycle state machine** gets a Mermaid state diagram and the fire→deliver→snooze flow a sequence diagram under `docs/diagrams/` (Principle IV requires state machines + key flows to be diagrammed). `docs/diagrams/er.md` is unchanged (no schema shape change; indexes only). Full spec-kit artifact set in this folder. Doc sweep reconciles `docs/glossary.md` + `docs/user_stories.md` UC-5.4 (`doses_remaining → refill_count`). |
| **V — Cross-Platform Tooling Integrity** | **PASS** | New tooling is **Python only** — `scripts/generate_vapid_keys.py` (no `.sh`/`.ps1` pair). The two new deps are pinned with upper bounds; `backend` lockfile/manifest updated and committed; `pip-audit` runs in CI. The scheduler is started in the FastAPI **lifespan**, gated by a settings flag so tests/CI and Alembic invocations don't spin it up. The Alembic revision keeps `alembic upgrade head && alembic check` green (new indexes are declared on the model). CI pipeline unchanged. |

**No violations.** Complexity Tracking section below is empty.

## Project Structure

### Documentation (this feature)

```text
specs/008-reminders-snooze/
├── plan.md                       # This file
├── spec.md                       # Feature spec (/speckit-specify + /speckit-clarify)
├── research.md                   # Phase 0 — decisions D1–D9
├── data-model.md                 # Phase 1 — existing tables + new indexes + reminder lifecycle
├── quickstart.md                 # Phase 1 — kickoff gate + per-story verification recipes
├── contracts/
│   └── reminders.openapi.yaml    # Phase 1 — pre-implementation API contract (push + reminders)
├── checklists/
│   ├── requirements.md           # Specify-stage merge gate (already green)
│   └── security.md               # NEW — Phase 7 security merge gate (push keys, scheduler, scoping)
└── tasks.md                      # Phase 2 output (/speckit-tasks; NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/medminder/
│   ├── domain/
│   │   ├── reminders.py              # NEW — PURE: next_dose_fire_times_utc, defer_for_quiet_hours
│   │   │                             #        (midnight-wrap), is_within_grace, crosses_refill_threshold
│   │   ├── reminder_dispatch.py      # NEW — async DB orchestration: generate / regenerate-for-schedule /
│   │   │                             #        dispatch_due / snooze / dismiss / resolve-on-take /
│   │   │                             #        ensure_refill_reminder / clear_refill_reminder
│   │   ├── push.py                   # NEW — pywebpush sender via asyncio.to_thread; classifies 404/410 (gone)
│   │   ├── doses.py                  # MODIFIED — create_dose: refill_count-- + ensure_refill_reminder +
│   │   │                             #        resolve dose reminder(s); void_dose: refill_count++
│   │   ├── medications.py            # MODIFIED — on update raising refill_count above threshold: clear refill warning
│   │   └── users.py                  # MODIFIED — update_user gains new_quiet_hours_start/_end (admin-managed config, U2)
│   ├── cli/
│   │   └── users.py                  # MODIFIED — `user update --quiet-hours-start/--quiet-hours-end` (admin-managed, U2)
│   ├── scheduler.py                  # NEW — build/start/shutdown AsyncIOScheduler; the recurring dispatch tick
│   ├── settings.py                   # MODIFIED — vapid_public_key/private_key/subject, reminders_enabled,
│   │                                 #        reminder_tick_seconds, reminder_grace_minutes, reminder_send_max_attempts
│   ├── app.py                        # MODIFIED — lifespan starts/stops the scheduler; mount push + reminders routers
│   ├── db/models/
│   │   └── reminders.py              # MODIFIED — add Index objects (dispatch scan, user/status, refill partial-unique)
│   ├── api/
│   │   ├── push.py                   # NEW — GET vapid-public-key; POST/DELETE push subscriptions
│   │   ├── reminders.py              # NEW — GET reminders; POST {id}/snooze; POST {id}/dismiss
│   │   ├── schedules_crud.py         # MODIFIED — create/update/delete → regenerate reminders for the schedule
│   │   ├── medications.py            # MODIFIED — save attach/detach → regenerate reminders for affected schedules
│   │   └── schemas/
│   │       ├── push.py               # NEW — VapidKeyOut, PushSubscriptionIn
│   │       └── reminders.py          # NEW — ReminderOut, ReminderListOut
│   └── alembic/versions/
│       └── 0006_reminder_indexes.py  # NEW — indexes + partial-unique refill dedup (no tables/columns)
└── tests/
    ├── domain/
    │   ├── test_reminders.py                 # NEW — pure fire-time / quiet-hours-wrap / grace / threshold
    │   ├── test_reminders_no_db_imports.py   # NEW — Principle III guard
    │   ├── test_reminder_dispatch.py         # NEW — generate/dispatch/snooze/dismiss/resolve (real PG, fake sender)
    │   ├── test_refill_supply.py             # NEW — decrement/restore + warn + dedup + re-arm
    │   └── test_push.py                      # NEW — sender success / gone-subscription cleanup (mocked pywebpush)
    └── api/
        ├── test_push_api.py                  # NEW — subscribe idempotent, unsubscribe, vapid key, cross-user
        └── test_reminders_api.py             # NEW — list / snooze / dismiss + cross-user (FR-017)

frontend/
├── public/
│   └── sw.js                          # NEW — minimal service worker: 'push' → showNotification, 'notificationclick' → focus app
├── src/
│   ├── api/v1.d.ts                    # REGENERATED — push + reminders endpoints/types
│   ├── lib/
│   │   └── push.ts                    # NEW — enable flow: permission → register SW → subscribe(VAPID) → POST
│   ├── hooks/
│   │   ├── usePushSubscription.ts     # NEW — enable/disable state + register/remove
│   │   ├── useReminders.ts            # NEW — list pending/snoozed/overdue
│   │   ├── useSnoozeReminder.ts       # NEW
│   │   └── useDismissReminder.ts      # NEW
│   ├── components/
│   │   └── reminders/
│   │       ├── EnableNotifications.tsx # NEW — minimal "Enable notifications" control
│   │       └── ReminderList.tsx        # NEW — in-app list with snooze/dismiss
│   ├── routes/
│   │   └── reminders.tsx              # NEW — reminders page (list + enable control)
│   ├── components/NavBar.tsx          # MODIFIED — add "Reminders" link
│   └── __tests__/
│       ├── EnableNotifications.test.tsx # NEW
│       └── ReminderList.test.tsx        # NEW
└── e2e/
    └── reminders.spec.ts             # NEW — Playwright (skip-gated): enable → due → in-app list → snooze

scripts/
└── generate_vapid_keys.py            # NEW — Python, prints a VAPID key pair for env config

docs/
├── adr/
│   └── 0002-in-process-apscheduler.md # MODIFIED — Status Proposed → Accepted; refined decision (reminders-table-as-truth)
├── diagrams/
│   ├── state-reminder-lifecycle.md    # NEW — Mermaid state diagram (pending→sent/snoozed/dismissed + overdue)
│   ├── sequence-reminder-dispatch.md  # NEW — Mermaid sequence (tick → generate → quiet-hours → push → mark sent)
│   └── README.md                      # MODIFIED — list the two new diagrams
├── glossary.md                        # MODIFIED — "Refill warning" fires on refill_count ≤ refill_threshold
└── user_stories.md                    # MODIFIED — UC-5.4 doses_remaining → refill_count; UC-5.2 in-app snooze (Phase 7)
```

**Structure Decision**: Existing web-monorepo layout (`backend/` + `frontend/`). Phase 7
follows established conventions: pure domain math in `domain/reminders.py` (mirroring
`domain/timezone.py` / `domain/timers.py`), async orchestration in a sibling module, new
routers beside the existing ones, schemas under `api/schemas/`, frontend tests mirroring the
source tree, Python-only tooling under `scripts/`, and Mermaid diagrams under
`docs/diagrams/`. The scheduler lives at `medminder/scheduler.py` (app-level, started in the
lifespan) so it sits above the domain layer and below the HTTP layer.

## Implementation Phasing

Sequenced for independently shippable slices following the spec priorities (US1 → US2/3/4/5
→ US6). Backend dispatch (B) underpins everything; the frontend (G) lands once the API exists.

- **Phase A — Baseline sanity gate (FIRST):** `python scripts/generate_openapi_client.py`
  and `cd backend && python -m alembic check` both clean before any change, so later drift is
  unambiguously Phase 7's. Re-run after the migration. (See `quickstart.md` Phase A.)
- **Phase B — Scheduler + dispatch core** (US1, FR-004/005/006/006a/007): pure
  `domain/reminders.py`; `domain/reminder_dispatch.py` generate + dispatch; `domain/push.py`;
  `scheduler.py`; settings + `app.py` lifespan wiring; the `0006` index migration.
- **Phase C — Subscriptions + in-app reminders API** (US1/US6, FR-001/002/008): `api/push.py`,
  `api/reminders.py`, schemas.
- **Phase D — Snooze + resolution** (US2, FR-009/010/021/022): snooze/dismiss orchestration +
  endpoints; `resolve_dose_reminders` hook in `create_dose`.
- **Phase E — Quiet hours** (US3, FR-011): `defer_for_quiet_hours` in the dispatcher.
- **Phase F — Schedule-mutation reschedule + live refill** (US4/US5, FR-012/013/014/014a):
  regeneration hooks in the schedules + medications routers; refill decrement/restore +
  warning dedup/re-arm in `domain/doses.py` / `domain/medications.py`.
- **Phase G — Frontend**: regenerate client; `sw.js`; `lib/push.ts` + hooks;
  `EnableNotifications`, `ReminderList`, `routes/reminders.tsx`; NavBar link.
- **Phase H — Cross-cutting** (FR-016/017/018/019/020): delivery resilience (retry + gone
  cleanup), cross-user negatives, secret-never-logged test, diagrams, ADR-0002 → Accepted,
  doc sweep, `checklists/security.md`, typing/lint/coverage gates.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

(no entries — all gates passed)
