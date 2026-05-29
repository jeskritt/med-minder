# Tasks: Phase 8 — PWA Polish

**Input**: Design documents from `/specs/010-pwa-polish/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/pwa-polish.openapi.yaml, quickstart.md

**Tests**: Included — the constitution mandates a coverage gate (≥85% overall, ≥70% per module)
and the plan enumerates specific test files. Test tasks accompany the implementation they cover.

**Organization**: Tasks are grouped by user story (spec priorities P1 → P3) so each story is an
independently testable increment. US1 (installable PWA) is the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 (user-story phases only)
- Paths are repo-relative. Frontend: `frontend/`, `frontend/src/`. Backend: `backend/src/medminder/`, tests `backend/tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Pinned build dependencies and the icon-generation script shared by the PWA work.

- [ ] T001 Baseline gate (quickstart Phase A): run `python scripts/generate_openapi_client.py` (no client diff) and `cd backend && python -m alembic check` (no drift), and record the current `frontend` dist bundle size from `pnpm build`, so later changes are unambiguously Phase 8's. No migration is added this phase.
- [ ] T002 Add pinned dev deps `vite-plugin-pwa` and `@vite-pwa/assets-generator` (with upper bounds, per Principle V) to `frontend/package.json`; refresh and commit `frontend/pnpm-lock.yaml`.
- [ ] T003 [P] Add a `"generate-pwa-assets"` pnpm script to `frontend/package.json` invoking `@vite-pwa/assets-generator`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Wire `vite-plugin-pwa` and author the single service worker every story builds on — it precaches the shell, keeps `/api` uncached, and ports the Phase 7 push handlers. Without this, no story can build or run.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [ ] T004 Configure `VitePWA` in `frontend/vite.config.ts` (`strategies: 'injectManifest'`, `srcDir: 'src'`, `filename: 'sw.ts'`, `registerType: 'prompt'`, `devOptions: { enabled: true }`, `injectManifest` glob for the built shell). Leave the `manifest` block for T012. (R1/R3)
- [ ] T005 Create the authored worker `frontend/src/sw.ts`: `precacheAndRoute(self.__WB_MANIFEST)`; a `NavigationRoute` serving the precached `index.html` with an `/api` **denylist**; an explicit **`NetworkOnly`** route for `/api` (never cached); and the **ported Phase 7** `push` (showNotification) + `notificationclick` (focus/open `/reminders`) handlers. (R1/R2/R4 — action buttons added in US4)
- [ ] T006 [P] Type the worker (R9): give `frontend/src/sw.ts` the WebWorker lib (dedicated tsconfig include or `/// <reference lib="webworker" />` + `declare const self: ServiceWorkerGlobalScope`) and add the `vite-plugin-pwa/client` types reference so `tsc --noEmit` stays strict; exclude generated `dev-sw.js`/`dist` SW output.
- [ ] T007 Create `frontend/src/lib/pwa.ts` — a `registerSW()` wrapper over `virtual:pwa-register` exposing an `onNeedRefresh` callback; call it from `frontend/src/main.tsx` (consumed by the UpdatePrompt in US3). (R3)
- [ ] T008 Remove `frontend/public/sw.js` and update `frontend/src/lib/push.ts` to stop hand-registering `/sw.js` — rely on the plugin-registered worker (`await navigator.serviceWorker.ready` before `pushManager.subscribe`). (R4)

**Checkpoint**: The app builds with one plugin-managed worker at `/sw.js` that precaches the shell and never caches `/api`; stories can begin.

---

## Phase 3: User Story 1 — Install MedMinder as an app (Priority: P1) 🎯 MVP

**Goal**: A valid manifest, a branded icon set, theme/background colors, and real `index.html` metadata so the app is installable and launches standalone; iOS gets an "Add to Home Screen" hint. (FR-001–004)

**Independent Test**: `pnpm build && pnpm preview` → DevTools Manifest shows name/icons/theme and "installable" with no errors; Lighthouse "installable" passes; on Android Chrome the native install affordance launches a standalone app with the MedMinder icon; on iOS Safari the in-app hint guides the Share-menu install.

### Implementation for User Story 1

- [ ] T009 [US1] Add the source brand asset `frontend/public/medminder.svg` (also usable as favicon).
- [ ] T010 [US1] Create `frontend/pwa-assets.config.ts` (e.g. `minimal-2023` preset) generating regular + maskable + apple-touch icons from `public/medminder.svg`.
- [ ] T011 [US1] Run `pnpm generate-pwa-assets` and **commit** the generated icons (`pwa-192x192.png`, `pwa-512x512.png`, maskable, `apple-touch-icon.png`) under `frontend/public/`. (R7)
- [ ] T012 [US1] Fill the `manifest` block in `frontend/vite.config.ts` `VitePWA(...)`: `name: "MedMinder"`, `short_name: "MedMinder"`, `description`, `start_url: "/"`, `scope: "/"`, `display: "standalone"`, `theme_color: "#0f172a"`, `background_color: "#f8fafc"`, and the icon set. (R7)
- [ ] T013 [US1] Update `frontend/index.html`: `<title>MedMinder</title>`, `<meta name="theme-color" content="#0f172a">`, and `<link rel="apple-touch-icon" href="/apple-touch-icon.png">` (the manifest link is plugin-injected). (FR-002)
- [ ] T014 [P] [US1] Create `frontend/src/components/pwa/InstallHint.tsx` — a dismissable iOS-only "Add to Home Screen" hint, shown only on iOS Safari when not already standalone. (R8/FR-002)
- [ ] T015 [US1] Mount `InstallHint` in the app shell `frontend/src/routes/__root.tsx`.
- [ ] T016 [P] [US1] Test `frontend/src/__tests__/InstallHint.test.tsx` — shows on iOS non-standalone, hidden on other platforms / when dismissed / when standalone.

**Checkpoint**: The app is installable and standalone-capable on Android Chrome and iOS Safari.

---

## Phase 4: User Story 2 — Understand and enable notifications without confusion (Priority: P2)

**Goal**: A contextual pre-prompt before the native dialog and clear per-state guidance (incl. denied→browser-settings recovery), reusing the Phase 7 subscription flow. (FR-010–013)

**Independent Test**: On `/reminders`, the default state shows a pre-prompt before the OS dialog and subscribes on accept; the denied state shows recovery guidance (no dead button); unsupported reassures reminders still appear in-app; an enabled device can turn off.

### Implementation for User Story 2

- [ ] T017 [US2] Rework `frontend/src/components/reminders/EnableNotifications.tsx`: add a contextual pre-prompt explaining reminders before calling `enablePushNotifications()`; render per-`PushStatus` UI for `default` / `subscribed` / `unsubscribed` / `denied` (with re-enable-in-settings guidance) / `unsupported`. (FR-010/011/013)
- [ ] T018 [US2] Verify/adjust `frontend/src/lib/push.ts` enable flow against the plugin-registered worker (await `ready` before subscribe; user-friendly error copy) — no change to the subscription API contract. (FR-012)
- [ ] T019 [P] [US2] Update `frontend/src/__tests__/EnableNotifications.test.tsx` to cover all states: pre-prompt precedes enable, denied shows recovery guidance, unsupported message, subscribed→turn-off.

**Checkpoint**: The push-permission flow is self-explanatory in every browser state; US1 still works.

---

## Phase 5: User Story 3 — Launch offline without a browser error (Priority: P2)

**Goal**: An offline indicator and a clean update flow over the foundational shell precache, so the installed app launches offline (shell, not an error page) and picks up new versions without a reload loop — and provably caches no API/PHI data. (FR-005–008)

**Independent Test**: Load once online, go offline, reload → the shell + offline banner render (not the browser error page); a data view shows a clear offline state with no stale medical data; a new build prompts to refresh and applies cleanly; the precache manifest contains no `/api` entries.

### Implementation for User Story 3

- [ ] T020 [P] [US3] Create `frontend/src/components/pwa/OfflineIndicator.tsx` — tracks `navigator.onLine` + `online`/`offline` events and renders a banner when offline. (R8/FR-005/007)
- [ ] T021 [P] [US3] Create `frontend/src/components/pwa/UpdatePrompt.tsx` — consumes the `onNeedRefresh` signal from `lib/pwa.ts` and offers "New version — refresh"; applying it triggers the waiting worker without an auto-reload loop. (R3/FR-008)
- [ ] T022 [US3] Mount `OfflineIndicator` and `UpdatePrompt` in `frontend/src/routes/__root.tsx` and wire `UpdatePrompt` to the `registerSW` update callback from `frontend/src/lib/pwa.ts`.
- [ ] T023 [P] [US3] Tests for offline UX (two small files): `frontend/src/__tests__/OfflineIndicator.test.tsx` — banner toggles with online/offline events; and `frontend/src/__tests__/offline-data-view.test.tsx` — a representative data view renders its offline/error state (**not stale data**) when its query fails, covering FR-007.
- [ ] T024 [P] [US3] Test `frontend/src/__tests__/sw-precache.test.ts` — assert the generated precache manifest lists only static shell assets and **no `/api`** entries. (FR-006/SC-004)

**Checkpoint**: Offline launch renders the shell, updates apply cleanly, and no PHI is cached; US1/US2 still work.

---

## Phase 6: User Story 4 — Act on a reminder from the notification (Priority: P3)

**Goal**: Snooze (1h) and Mark-taken action buttons on dose notifications, handled in the SW; "Mark taken" calls a new reminder-id-keyed endpoint that records a dose per attached med atomically and fails safe on any guard. (FR-014–016)

**Independent Test**: Backend — a slot with N meds records N doses + resolves (204); any guard → 409 with zero doses committed (atomic); already-resolved/no-meds → 204; cross-user → 404. Manual — with the app closed, "Snooze" re-fires ~1h later; "Mark taken" records and resolves (or shows an "open the app" notice when guard-blocked); tapping the body opens `/reminders`.

### Implementation for User Story 4

- [ ] T025 [US4] Add `take_reminder(session, *, user, reminder_id, now)` to `backend/src/medminder/domain/reminder_dispatch.py`: load the caller-owned reminder (`_load_owned_reminder` → `ReminderNotFoundError`); require `type='dose'` with a `schedule_id`; resolve the slot's **non-deleted** attached meds (the `ScheduleMedication`⋈`Schedule` pattern from `domain/doses.py`); record a dose for **each** via `create_dose(... taken_at=now, interaction_acknowledged=False)`; then `resolve_dose_reminders(...)`. Guard errors **propagate — do NOT catch them**: the request-level `session.begin()` in `get_session` (`api/deps.py:29`) rolls back on the exception, so no dose commits (atomic). (R5/R6)
- [ ] T026 [US4] Add `POST /{reminder_id}/take` to `backend/src/medminder/api/reminders.py` calling `take_reminder`: map `ReminderNotFoundError` → 404 and a non-dose/refill reminder → 422, and return **204** on success/idempotent. **No new guard→409 mapping is needed** — the four **app-wide** `@app.exception_handler`s in `app.py:112-171` (`MinIntervalNotElapsedError`/`WindowFullError`/`DailyCapReachedError`/`MedicationInteractionConflictError`) already render the existing 409 violation bodies for *any* route, so the take endpoint inherits them as long as `take_reminder` lets the guard exceptions propagate (T025). (R6 / contracts/pwa-polish.openapi.yaml)
- [ ] T027 [P] [US4] Tests in `backend/tests/api/test_reminders_api.py` (take): take-all records N doses + resolves (204); any guard (e.g. window-full or interaction cooldown) → 409 and the dose row count is **unchanged** (atomic rollback); already-resolved / no-meds → idempotent 204; cross-user → 404; refill reminder → 422. (FR-015/016, SC-006)
- [ ] T028 [US4] Regenerate the client: `python scripts/generate_openapi_client.py` → `frontend/src/api/v1.d.ts` includes `reminders_take`; confirm `alembic check` is still clean (no migration). (ADR-0003)
- [ ] T029 [US4] Enhance the `push` handler in `frontend/src/sw.ts`: for `data.type === 'dose'`, add notification `actions` `[{ action: 'snooze', title: 'Snooze 1h' }, { action: 'take', title: 'Mark taken' }]`. (FR-014)
- [ ] T030 [US4] Enhance the `notificationclick` handler in `frontend/src/sw.ts`: branch on `event.action` — `'snooze'` → `POST /api/v1/reminders/{id}/snooze`; `'take'` → `POST /api/v1/reminders/{id}/take` (both `fetch(..., { credentials: 'include' })`); on a non-2xx response show a fail-safe "Couldn't record — open the app" notification; no action (body tap) → open `/reminders` (Phase 7 behavior preserved). (FR-014/015/016)

**Checkpoint**: All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns (FR-017–020)

**Purpose**: ADR, diagrams, security gate, doc sweep, and the full quality/acceptance gates.

- [ ] T031 [P] Author `docs/adr/0015-pwa-service-worker.md` — the PWA/SW strategy: `vite-plugin-pwa` injectManifest, app-shell-only precache, the rationale for never caching API/PHI, the prompt-to-refresh update flow, and SW-handled notification actions. (FR-020)
- [ ] T032 [P] Add `docs/diagrams/sequence-notification-action.md` (Mermaid: tap "Mark taken" → SW → `take` → guards/atomic → resolve / fail-safe notify) and list it in `docs/diagrams/README.md`. (FR-020)
- [ ] T033 [P] Add `specs/010-pwa-polish/checklists/security.md` merge gate: no PHI in caches (T024), `take` endpoint user-scoped + atomic + never auto-acknowledges interactions, VAPID secrets untouched, SW scope limited to the app origin. (FR-017)
- [ ] T034 Doc sweep: add a Phase 8 behavior note bullet to `CLAUDE.md` (installable PWA via vite-plugin-pwa/injectManifest, app-shell-only cache with `/api` never cached, polished push UX, and the new `POST /reminders/{id}/take` reminder-id-keyed atomic take-all with guard fail-safe).
- [ ] T035 **Verify no `routeTree.gen.ts` drift** — Phase 8 mounts components in `__root.tsx` and adds no new routes under `routes/`, so the route tree should be unchanged. Only if a route was actually added: regenerate `frontend/src/routeTree.gen.ts` **on the host** (EXDEV under docker — [[project_routetree_exdev_docker]]) and re-run `tsc`.
- [ ] T036 Quality gates: `just lint`, `just typecheck` (incl. the worker tsconfig), `just test` (coverage ≥85%, no module < 70%), and `cd frontend && pnpm audit` (no un-triaged high-severity in the new deps). (FR-018/019)
- [ ] T037 Manual acceptance per `quickstart.md`: Lighthouse "installable" passes (SC-002); offline launch renders the shell (SC-003); real-device install on iOS Safari + Android Chrome (SC-001); notification Snooze + Mark-taken incl. guard fail-safe (SC-006); update flow with no reload loop (SC-007).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories** (the plugin + worker + registration underpin every story).
- **User Stories (Phase 3–6)**: All depend on Foundational. US1 → US2 → US3 → US4 in priority order; US1–US3 are largely independent once Foundational is done. US4 has an internal backend→client→SW order.
- **Polish (Phase 7)**: Depends on the desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: After Foundational. Independent (manifest/icons/html/install hint). MVP.
- **US2 (P2)**: After Foundational. Independent (touches only `EnableNotifications.tsx` + `push.ts`).
- **US3 (P2)**: After Foundational. Independent (offline/update UI + the no-`/api` cache test).
- **US4 (P3)**: After Foundational. Backend take endpoint (T025–T027) is independent; the SW handlers (T029/T030) depend on the regenerated client (T028) and the foundational `src/sw.ts` (T005).

### Within / across stories — file-contention notes

- `frontend/src/sw.ts`: authored in T005, extended in T029/T030 → **sequential** (same file).
- `frontend/src/routes/__root.tsx`: edited by T015 (US1) and T022 (US3) → **sequential**.
- `frontend/vite.config.ts`: T004 (foundational) then T012 (US1 manifest) → sequential.
- `frontend/src/lib/push.ts`: edited by T008 (foundational, drop self-registration) then T018 (US2, verify enable flow) → **sequential**.

### Parallel Opportunities

- T003 in Setup.
- T006 alongside T005/T007/T008 (different files) in Foundational.
- T014 + T016 within US1; T019 within US2; T020 + T021 + T023 + T024 within US3; T027 within US4.
- Polish T031 + T032 + T033 are parallel (different files).
- With multiple developers, after Foundational: US1, US2, and US3 can proceed in parallel; US4 in parallel too (its backend half is independent).

---

## Parallel Example: User Story 3

```bash
# After Foundational, launch the independent US3 pieces together:
Task: "Create OfflineIndicator.tsx in frontend/src/components/pwa/"
Task: "Create UpdatePrompt.tsx in frontend/src/components/pwa/"
Task: "Test OfflineIndicator in frontend/src/__tests__/OfflineIndicator.test.tsx"
Task: "Test no-/api precache in frontend/src/__tests__/sw-precache.test.ts"
# Then T022 (mount in __root.tsx) runs after T020/T021.
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (CRITICAL — blocks all stories) → 3. Phase 3 US1.
4. **STOP and VALIDATE**: install on a real device + Lighthouse "installable". 5. Demo the installable app.

### Incremental Delivery

1. Setup + Foundational → the plugin-managed shell worker exists.
2. US1 → installable PWA (MVP) → validate → demo.
3. US2 → polished push permission UX → validate → demo.
4. US3 → offline shell + clean updates (provably no PHI cached) → validate → demo.
5. US4 → notification Snooze/Mark-taken → validate → demo.
6. Polish → ADR, diagram, security gate, doc sweep, quality + manual acceptance gates.

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- [Story] label maps each task to its user story for traceability.
- The single biggest security invariant is **"never cache `/api`"** — keep T024 green.
- The `take` endpoint must never auto-acknowledge interaction cooldowns and must be atomic — keep T027 green.
- No database migration this phase; `alembic check` stays clean throughout.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
