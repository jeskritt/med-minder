# Tasks: Phase 7 — Reminders + Snooze

**Input**: Design documents from `/specs/008-reminders-snooze/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/reminders.openapi.yaml, quickstart.md

**Tests**: Included — the constitution mandates a coverage gate (≥85% overall, ≥70% per module)
and the plan enumerates specific test files. Test tasks precede the implementation they cover.

**Organization**: Tasks are grouped by user story (spec priorities P1 → P3) so each story is an
independently testable increment. US1 is the MVP (the scheduling + push engine).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US6 (user-story phases only)
- Paths are repo-relative. Backend: `backend/src/medminder/`, tests `backend/tests/`. Frontend: `frontend/src/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies, settings, and tooling shared by every story.

- [ ] T001 Baseline gate (quickstart Phase A): run `python scripts/generate_openapi_client.py` then confirm `git diff --exit-code frontend/src/api/v1.d.ts` is clean, and `cd backend && python -m alembic upgrade head && python -m alembic check` reports no drift — so later drift is unambiguously Phase 7's.
- [ ] T002 Add pinned runtime deps `apscheduler>=3.11,<4.0` and `pywebpush>=2.0,<3.0` to `backend/pyproject.toml` and refresh/commit the backend lockfile.
- [ ] T003 [P] Add reminder/push settings to `backend/src/medminder/settings.py`: `vapid_public_key`, `vapid_private_key` (secret), `vapid_subject`, `reminders_enabled` (default True), `reminder_tick_seconds` (default 30), `reminder_grace_minutes` (default 15), `reminder_send_max_attempts` (default 3).
- [ ] T004 [P] Create `scripts/generate_vapid_keys.py` (Python, cross-platform per Principle V) that prints a VAPID public/private key pair + a suggested `VAPID_SUBJECT`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema indexes + the pure scheduling-math module every story imports.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [ ] T005 Add `Index` objects to `backend/src/medminder/db/models/reminders.py`: `ix_reminders_dispatch` (partial on `scheduled_for` WHERE `status='pending'`), `ix_reminders_user_status` (`user_id, status`), and partial-UNIQUE `uq_reminders_open_refill` on `medication_id` WHERE `type='refill' AND status <> 'dismissed'`.
- [ ] T006 Generate the Alembic revision `backend/alembic/versions/0006_reminder_indexes.py` via `just migrate-rev "phase 7 reminder indexes"` (indexes only — no tables/columns); run `python -m alembic upgrade head && python -m alembic check` and confirm clean.
- [ ] T007 [P] Create the PURE module `backend/src/medminder/domain/reminders.py` with `next_dose_fire_times_utc(time_of_day, days_of_week, tz, now, horizon)` and `is_within_grace(scheduled_for, now, grace)` — NO sqlalchemy/fastapi/apscheduler imports (quiet-hours and refill helpers are added in their story phases).
- [ ] T008 [P] Add `backend/tests/domain/test_reminders_no_db_imports.py` asserting `domain/reminders.py` imports no DB/HTTP/scheduler modules (Principle III guard, mirrors the Phase 5/6 analogue).

**Checkpoint**: Migration is drift-free and the pure math module exists — stories can begin.

---

## Phase 3: User Story 1 — Get a push reminder when a scheduled dose is due (Priority: P1) 🎯 MVP

**Goal**: Generate dose reminders per schedule slot, fire them on an in-process tick, and
deliver Web Push to enabled devices; reminders are also listable in-app. (FR-001–008, 006a)

**Independent Test**: Enable notifications, set a schedule slot ~1 min out with a med attached
→ within a tick a push arrives naming the med and the reminder flips `pending → sent`; with no
subscription the slot still shows in `GET /api/v1/reminders` and no send is attempted; pending
reminders survive a restart.

### Tests for User Story 1

- [ ] T009 [P] [US1] `backend/tests/domain/test_reminders.py` — pure `next_dose_fire_times_utc` (days-of-week mask, user tz → UTC) and `is_within_grace`.
- [ ] T010 [P] [US1] `backend/tests/domain/test_reminder_dispatch.py` — `generate_due_dose_reminders` (idempotent, per-slot, names attached meds) and `dispatch_due_reminders` (within-grace push + mark sent; overdue stays pending; coalesce) against real Postgres with a fake `send`.
- [ ] T011 [P] [US1] `backend/tests/domain/test_push.py` — `domain/push.py` send success and 404/410-gone classification (pywebpush mocked; assert the VAPID private key / `auth` / `p256dh` never appear in any log capture, SC-009).
- [ ] T012 [P] [US1] `backend/tests/api/test_push_api.py` — `GET vapid-public-key`, idempotent `POST subscriptions`, `DELETE subscriptions`, and a cross-user negative (FR-017).
- [ ] T013 [P] [US1] `backend/tests/api/test_reminders_api.py` — `GET /api/v1/reminders` returns only the caller's open reminders (pending/overdue/snoozed/unresolved-sent), excludes dismissed, and is cross-user isolated.

### Implementation for User Story 1

- [ ] T014 [US1] Implement `generate_due_dose_reminders(session, *, now, horizon)` in `backend/src/medminder/domain/reminder_dispatch.py` — idempotent upsert of `pending` dose reminders for each (schedule, fire-instant) within the horizon for non-deleted schedules with ≥1 attached non-deleted med (uses T007 pure math).
- [ ] T015 [US1] Implement `dispatch_due_reminders(session, *, now, grace, send)` in `backend/src/medminder/domain/reminder_dispatch.py` — select due `pending` rows, push within grace + mark `sent`, leave older-than-grace as overdue `pending`; best-effort per-subscription send (depends on T014, same file).
- [ ] T016 [P] [US1] Implement `domain/push.py` in `backend/src/medminder/domain/push.py` — `send_web_push(subscription, payload, settings)` via `asyncio.to_thread(pywebpush...)`; raise/return a result that flags 404/410 as gone; single scoped `# type: ignore[import-untyped]` with rationale at the import.
- [ ] T017 [US1] Implement `backend/src/medminder/scheduler.py` — `build_scheduler(settings, session_factory)` (`AsyncIOScheduler`, default in-memory job store, single recurring tick id with `replace_existing=True`) whose tick opens a session and calls generate + dispatch (injecting `domain/push.send_web_push`); `start`/`shutdown` helpers (depends on T014–T016).
- [ ] T018 [US1] Wire the scheduler into `backend/src/medminder/app.py` lifespan — build/start on startup when `settings.reminders_enabled`, shutdown on exit; stash on `app.state` (depends on T017).
- [ ] T019 [P] [US1] Create `backend/src/medminder/api/schemas/push.py` — `VapidKeyOut`, `PushSubscriptionIn` (endpoint + keys{p256dh, auth}), `PushUnsubscribeIn` (Pydantic strict, `extra="forbid"`).
- [ ] T020 [P] [US1] Create `backend/src/medminder/api/schemas/reminders.py` — `ReminderOut` (id, type, status, scheduled_for, title, schedule_id?, medication_id?, overdue) and `ReminderListOut`.
- [ ] T021 [US1] Create `backend/src/medminder/api/push.py` router — `GET /api/v1/push/vapid-public-key`, idempotent `POST /api/v1/push/subscriptions`, `DELETE /api/v1/push/subscriptions`, all `Depends(get_current_user)` and user-scoped (depends on T019).
- [ ] T022 [US1] Create `backend/src/medminder/api/reminders.py` router — `GET /api/v1/reminders` listing the caller's open reminders with computed `title`/`overdue` (depends on T020).
- [ ] T023 [US1] Mount the push + reminders routers in `backend/src/medminder/app.py` (depends on T021, T022).
- [ ] T024 [US1] Regenerate `frontend/src/api/v1.d.ts` via `python scripts/generate_openapi_client.py` and confirm no unexpected drift (depends on T021–T023).
- [ ] T025 [P] [US1] Create the minimal service worker `frontend/public/sw.js` — `push` event → `showNotification` with the payload; `notificationclick` → focus/open the app.
- [ ] T026 [P] [US1] Create `frontend/src/lib/push.ts` + `frontend/src/hooks/usePushSubscription.ts` — enable flow: check `Notification.permission`, register `/sw.js`, fetch the VAPID public key, `PushManager.subscribe`, POST the subscription; expose enabled/disable state.
- [ ] T027 [P] [US1] Create `frontend/src/hooks/useReminders.ts` — TanStack Query hook for `GET /api/v1/reminders`.
- [ ] T028 [US1] Create `frontend/src/components/reminders/EnableNotifications.tsx`, `frontend/src/components/reminders/ReminderList.tsx`, and `frontend/src/routes/reminders.tsx`; add a "Reminders" link in `frontend/src/components/NavBar.tsx` (depends on T024, T026, T027).
- [ ] T029 [P] [US1] Add `frontend/src/__tests__/EnableNotifications.test.tsx` and `frontend/src/__tests__/ReminderList.test.tsx` (vitest + Testing Library).

**Checkpoint**: A scheduled dose reminder is generated, fired on the tick, delivered via push to an enabled device, and visible in-app — independently demoable.

---

## Phase 4: User Story 2 — Snooze + resolve a reminder (Priority: P2)

**Goal**: In-app snooze (1h, re-snoozeable), manual dismiss, and auto-resolve on take — the
reminder-action cluster. (FR-009, 010, 021, 022)

**Independent Test**: Snooze a visible reminder → original `snoozed`, new `pending` at +1h;
dismiss a reminder → `dismissed` and gone from the list; take a dose for a slot with a pending
reminder → that reminder auto-resolves; snoozing/dismissing another user's reminder → 404.

### Tests for User Story 2

- [ ] T030 [P] [US2] `backend/tests/domain/test_reminder_actions.py` — `snooze_reminder` (marks `snoozed` + creates +1h `pending`; re-snooze), `dismiss_reminder` (idempotent), `resolve_dose_reminders` (only that slot, today, pending/snoozed) against real Postgres.
- [ ] T031 [P] [US2] `backend/tests/api/test_reminders_actions.py` — `POST {id}/snooze` returns the next reminder, `POST {id}/dismiss` → 204 idempotent, both 404 for another user's reminder (FR-017).

### Implementation for User Story 2

- [ ] T032 [US2] Add `snooze_reminder`, `dismiss_reminder`, and `resolve_dose_reminders` to `backend/src/medminder/domain/reminder_dispatch.py` (depends on T014/T015, same file).
- [ ] T033 [US2] Add `POST /api/v1/reminders/{id}/snooze` and `POST /api/v1/reminders/{id}/dismiss` to `backend/src/medminder/api/reminders.py` (ownership-checked; 404 otherwise) (depends on T032, T022).
- [ ] T034 [US2] Call `resolve_dose_reminders` from `create_dose` in `backend/src/medminder/domain/doses.py` (same transaction, after the dose insert) (FR-021).
- [ ] T035 [US2] Regenerate the client; add `frontend/src/hooks/useSnoozeReminder.ts` + `frontend/src/hooks/useDismissReminder.ts`; wire snooze/dismiss buttons into `frontend/src/components/reminders/ReminderList.tsx` (depends on T033).

**Checkpoint**: Reminders can be snoozed/dismissed in-app and clear automatically when the dose is taken.

---

## Phase 5: User Story 3 — Respect quiet hours (Priority: P2)

**Goal**: Defer reminders due inside the user's quiet-hours window to the window end, with
correct midnight-wrap. (FR-011)

**Independent Test**: Set quiet hours containing a slot time → no push during the window;
delivery at the window end; 02:00 with 22:00→07:00 defers to 07:00; no quiet hours → immediate.

### Tests for User Story 3

- [ ] T036 [P] [US3] `backend/tests/domain/test_reminders_quiet_hours.py` — pure `defer_for_quiet_hours` covering inside-window, wrap-midnight, boundary-exclusive-at-end, and no-quiet-hours cases.
- [ ] T036b [P] [US3] `backend/tests/cli/test_users_quiet_hours.py` — `user update --quiet-hours-start/--quiet-hours-end` sets and clears the columns; invalid time format is rejected.

### Implementation for User Story 3

- [ ] T036a [US3] Add a quiet-hours configuration path (FR-011 enabler — quiet hours are admin-managed like `timezone`): extend `update_user` in `backend/src/medminder/domain/users.py` with `new_quiet_hours_start`/`new_quiet_hours_end` (set or clear, validated) and add `--quiet-hours-start`/`--quiet-hours-end` options to `user update` in `backend/src/medminder/cli/users.py`. (No in-app editor in Phase 7.)
- [ ] T037 [US3] Add `defer_for_quiet_hours(fire_utc, tz, qh_start, qh_end)` to the pure `backend/src/medminder/domain/reminders.py` (returns the deferred UTC instant or `None`) (extends T007, same file).
- [ ] T038 [US3] Apply deferral in `dispatch_due_reminders` (`backend/src/medminder/domain/reminder_dispatch.py`) — when deferred, update the row's `scheduled_for` and leave it `pending` instead of pushing (depends on T037, T015).
- [ ] T039 [US3] Add a quiet-hours deferral integration case (incl. midnight wrap) to `backend/tests/domain/test_reminder_dispatch.py`.

**Checkpoint**: Reminders never push during quiet hours and arrive at the window end.

---

## Phase 6: User Story 4 — Reminders follow schedule edits (Priority: P2)

**Goal**: Schedule create/edit/delete and med attach/detach (re)generate or cancel the affected
future dose reminders, leaving history intact. (FR-012)

**Independent Test**: Edit a schedule's time → future pending reminders move; delete → cancelled;
attach/detach a med → generation follows; after any mutation the pending set matches current state.

### Tests for User Story 4

- [ ] T040 [P] [US4] `backend/tests/api/test_schedule_reminder_sync.py` — create/update/delete schedule and attach/detach med each leave the pending dose-reminder set matching current state with zero stale/missing (SC-005); past `sent`/`dismissed` untouched.

### Implementation for User Story 4

- [ ] T041 [US4] Add `regenerate_schedule_reminders(session, *, schedule_id)` to `backend/src/medminder/domain/reminder_dispatch.py` — delete future `pending` dose reminders for the schedule, then regenerate from current state.
- [ ] T042 [US4] Call `regenerate_schedule_reminders` from `create_schedule`/`update_schedule`/`delete_schedule` in `backend/src/medminder/api/schedules_crud.py` (within the existing transaction) (depends on T041).
- [ ] T043 [US4] Call `regenerate_schedule_reminders` for affected schedules from the medication save (attach/detach) path in `backend/src/medminder/api/medications.py` (depends on T041).

**Checkpoint**: Reminders always reflect the live schedule state — the ADR-0009 "reminders shift" promise is real.

---

## Phase 7: User Story 5 — Refill warning on live supply (Priority: P2)

**Goal**: `refill_count` decrements on take / restores on void; a refill warning fires when it
reaches `refill_threshold` (opt-in), deduped to one open warning per med and re-armed on refill.
(FR-013, 014, 014a, 015)

**Independent Test**: Take doses → count decrements (floored at 0); at/below threshold a refill
warning is generated naming the med + remaining; repeat take → no duplicate; void → restores;
edit count back above threshold → warning resolves and can fire again; no threshold → never warns.

### Tests for User Story 5

- [ ] T044 [P] [US5] `backend/tests/domain/test_refill_supply.py` — decrement/restore (floor at 0), warn-at-threshold, opt-in (no threshold → no warn), dedup (no second open warning), and re-arm on raising count above threshold.

### Implementation for User Story 5

- [ ] T045 [US5] Add `crosses_refill_threshold(before, after, threshold)` to the pure `backend/src/medminder/domain/reminders.py` (extends T007, same file).
- [ ] T046 [US5] Add `ensure_refill_reminder(session, *, user, medication)` and `clear_refill_reminder(session, *, medication)` to `backend/src/medminder/domain/reminder_dispatch.py` (respect the `uq_reminders_open_refill` dedup invariant).
- [ ] T047 [US5] In `backend/src/medminder/domain/doses.py`: decrement `refill_count` (floored at 0) + call `ensure_refill_reminder` on a downward threshold crossing in `create_dose`; in `void_dose` restore `refill_count` by one **only when it is set** (skip when NULL, so a void never restores into an untracked med — FR-013) (depends on T045, T046). Cover the NULL-count void in `tests/domain/test_refill_supply.py` (T044).
- [ ] T048 [US5] In the medication update path (`backend/src/medminder/domain/medications.py`): when `refill_count` is raised back above `refill_threshold`, call `clear_refill_reminder` (FR-014a) (depends on T046).
- [ ] T049 [US5] Confirm refill reminders render in `frontend/src/components/reminders/ReminderList.tsx` (they flow through `GET /api/v1/reminders`); add a refill-type case to `frontend/src/__tests__/ReminderList.test.tsx`.

**Checkpoint**: Supply is live and refill warnings fire once per low-supply episode.

---

## Phase 8: User Story 6 — Resilient delivery (Priority: P3)

**Goal**: Bounded retry on transient push failure, cleanup of gone subscriptions, and an in-app
fallback when push permission is denied. (FR-016, FR-008)

**Independent Test**: A 410 on send removes that subscription; a transient error retries then
gives up without crashing the tick; with no subscription the in-app list still shows due reminders.

### Tests for User Story 6

- [ ] T050 [P] [US6] `backend/tests/domain/test_push_resilience.py` — transient error → retried up to `reminder_send_max_attempts` (default 3) then give-up (no exception escapes the tick); 404/410 → subscription deleted.
- [ ] T051 [P] [US6] `backend/tests/api/test_reminders_no_subscription.py` — with no push subscription, reminders still generate and `GET /api/v1/reminders` lists them (push best-effort, FR-008).

### Implementation for User Story 6

- [ ] T052 [US6] Add bounded retry + gone-subscription deletion to the dispatch send path (`backend/src/medminder/domain/reminder_dispatch.py` + `backend/src/medminder/domain/push.py`): catch per-send exceptions, retry transient up to `reminder_send_max_attempts` (default 3), delete the subscription on 404/410, never let a send abort the batch (depends on T015, T016).

**Checkpoint**: Push flakiness is handled and the in-app channel is a reliable fallback.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, diagrams, the security merge gate, and the final quality gates.

- [ ] T053 [P] Promote ADR-0002 `Proposed → Accepted` in `docs/adr/0002-in-process-apscheduler.md`, documenting the refined approach (reminders-table-as-truth + recurring tick; default in-memory job store; why not `SQLAlchemyJobStore` — the DML-only runtime role) per research D1.
- [ ] T054 [P] Add the reminder-lifecycle Mermaid state diagram `docs/diagrams/state-reminder-lifecycle.md` (pending→sent/snoozed/dismissed + overdue, per data-model.md).
- [ ] T055 [P] Add the dispatch sequence diagram `docs/diagrams/sequence-reminder-dispatch.md` (tick → generate → quiet-hours defer → push → mark sent) and list both new diagrams in `docs/diagrams/README.md`.
- [ ] T056 [P] Doc sweep: in `docs/glossary.md` and `docs/user_stories.md` UC-5.4, change the refill-warning trigger from `doses_remaining` to `refill_count ≤ refill_threshold`; in UC-5.2 note snooze is in-app for Phase 7; document the new `user update --quiet-hours-start/--quiet-hours-end` flags in `backend/README.md` (alongside the existing CLI docs).
- [ ] T057 [P] Add a Phase 7 reminders bullet to the "Things that have surprised people" section of `CLAUDE.md` (in-process scheduler, reminders-table-as-truth, `refill_count` live, in-app snooze, single instance).
- [ ] T058 [P] Update `docs/deployment.md`: single-instance scheduler requirement, `REMINDERS_ENABLED`, and the VAPID env vars (private key is secret).
- [ ] T059 Create the security merge gate `specs/008-reminders-snooze/checklists/security.md` (user-scoping of all endpoints, VAPID private key never exposed/logged, subscription-secret minimisation, cross-user negatives, scheduler single-instance).
- [ ] T060 Final gates: `just lint`, `just typecheck` (mypy --strict + tsc --noEmit), `just test` (coverage ≥85% overall / ≥70% per module), `cd backend && python -m alembic check`, and `python scripts/generate_openapi_client.py && git diff --exit-code frontend/src/api/v1.d.ts`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories** (the migration and the pure module).
- **User Stories (Phase 3–8)**: all depend on Foundational. US1 underpins delivery; US2–US6 build on US1's dispatch/reminders surface. Within a story, tests precede implementation.
- **Polish (Phase 9)**: depends on the implemented stories.

### User Story Dependencies

- **US1 (P1)**: after Foundational. The MVP engine (generate + dispatch + push + subscribe + in-app list).
- **US2 (P2)**: after US1 (reuses `reminder_dispatch.py` + the reminders router + create_dose).
- **US3 (P2)**: after US1 (extends the pure module + dispatch). Independent of US2.
- **US4 (P2)**: after US1 (adds regeneration; hooks the schedule/med routers). Independent of US2/US3.
- **US5 (P2)**: after US1 (adds refill helpers; hooks doses/medications). Independent of US2–US4.
- **US6 (P3)**: after US1 (hardens the send path). Independent of US2–US5.

> Note: US2/US3/US5/US6 each edit `domain/reminder_dispatch.py` and/or the pure `domain/reminders.py`; if worked in parallel, serialize edits to those two shared files (they are not marked [P] across stories).

### Within Each User Story

Tests (written to fail first) → pure/domain → orchestration → endpoints → app wiring → frontend.

### Parallel Opportunities

- Setup: T003, T004 in parallel.
- Foundational: T007, T008 in parallel (after T005/T006).
- US1 tests T009–T013 in parallel; schemas T019/T020 and frontend leaves T025/T026/T027 in parallel; `domain/push.py` (T016) parallel with the dispatch work.
- Each later story's test task is [P]; cross-story parallelism is possible once US1 lands, subject to the shared-file note above.

---

## Parallel Example: User Story 1

```bash
# Tests first (all different files):
Task: T009 backend/tests/domain/test_reminders.py
Task: T010 backend/tests/domain/test_reminder_dispatch.py
Task: T011 backend/tests/domain/test_push.py
Task: T012 backend/tests/api/test_push_api.py
Task: T013 backend/tests/api/test_reminders_api.py

# Then parallel leaves:
Task: T016 backend/src/medminder/domain/push.py
Task: T019 backend/src/medminder/api/schemas/push.py
Task: T020 backend/src/medminder/api/schemas/reminders.py
Task: T025 frontend/public/sw.js
Task: T026 frontend/src/lib/push.ts
Task: T027 frontend/src/hooks/useReminders.ts
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & VALIDATE** the
   enable → due → push → in-app loop (quickstart US1) → demo. This is the shippable MVP.

### Incremental Delivery

US1 (MVP) → US2 (snooze/dismiss/resolve) → US3 (quiet hours) → US4 (reschedule) →
US5 (live refill) → US6 (resilience) → Phase 9 (docs/diagrams/ADR/security gate/final gates).
Each story is independently testable and adds value without breaking the previous ones.

### Notes

- `[P]` = different files, no incomplete dependency. The two shared backend files
  (`domain/reminders.py`, `domain/reminder_dispatch.py`) are edited by several stories — serialize those.
- Run the scheduler only with `reminders_enabled` (off in tests/CI/Alembic); test the domain
  functions directly with a fake `send`.
- Keep the VAPID private key and subscription secrets out of logs and responses (SC-009) — assert it in tests.
- Per the project convention, branching/committing is the user's call (not part of these tasks).
