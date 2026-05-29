# ADR-0015 — PWA service worker: vite-plugin-pwa (injectManifest), app-shell-only caching

## Status

**Accepted** (Phase 8 — PWA polish).

## Context

Phase 7 shipped Web Push with a minimal hand-written `frontend/public/sw.js` (push +
notificationclick only) and explicitly deferred the PWA polish to Phase 8: an installable
app, an offline app shell, a polished permission flow, and notification action buttons.
We had to decide how to build and structure the service worker, what to cache, and how the
notification "Mark taken"/"Snooze" actions act on the server.

Constraints that shaped the decision:

- **No PHI in caches** (Principle I). MedMinder data is treated as protected health
  information; an installed app may live on a shared device.
- The worker must **keep the Phase 7 push logic** and **cleanly replace** the existing
  `/sw.js` (no duplicate push handlers / double notifications).
- The stack is React 19 + **Vite 8** (Rolldown) with `tsc --noEmit` strict typing and pnpm.

## Decision

**Use `vite-plugin-pwa` with the `injectManifest` strategy** and an authored worker at
`frontend/src/sw.ts`:

- **injectManifest, not generateSW** — the worker hosts custom logic (push, notificationclick,
  and the new snooze/take notification actions) that generateSW can't express cleanly.
  Workbox precaching is pulled in via `precacheAndRoute(self.__WB_MANIFEST)`.
- **App-shell-only caching.** The worker precaches only the static build output
  (`globPatterns` of `js/css/html/svg/png/ico/woff2`) and serves the precached `index.html`
  for SPA navigations via a `NavigationRoute`. **`/api` is denylisted from the navigation
  fallback and has no runtime caching route**, so no authenticated/medical response is ever
  written to Cache Storage (FR-006/SC-004). A source-level test (`sw-precache.test.ts`)
  enforces this.
- **Controlled updates** (`registerType: 'prompt'`). Registration is manual (`lib/pwa.ts`
  over `virtual:pwa-register`); a new shell waits behind an in-app "Refresh" prompt
  (`UpdatePrompt`) — no auto-`skipWaiting` reload loop (FR-008).
- **Same `/sw.js` scope** as Phase 7, so the new worker upgrades the old registration in
  place; `lib/push.ts` stops self-registering and reuses the plugin-registered worker.
- **Notification actions are reminder-id-keyed and server-authoritative.** Snooze reuses
  `POST /reminders/{id}/snooze`; "Mark taken" calls the new `POST /reminders/{id}/take`,
  which records a dose for every medication attached to the slot and resolves the reminder.
  The push payload is **not** expanded with medical ids (the SW already has `reminder_id`).
  The take is **atomic** via the request transaction: any overdose/interaction guard
  (`create_dose` validates before inserting) propagates as a 409 with nothing committed, and
  an interaction cooldown is **never** auto-acknowledged from a notification — the SW shows a
  "open the app" fail-safe instead (FR-015/FR-016).
- **Worker typing.** `src/sw.ts` is type-checked under a dedicated `tsconfig.worker.json`
  (WebWorker lib), excluded from the DOM-typed app/test configs (Principle II).

Icons are generated from one source asset (`@vite-pwa/assets-generator`, `minimal-2023`) and
committed, keeping the build deterministic.

## Consequences

### Positive
- Installable, offline-launchable PWA with the Phase 7 push loop intact.
- The "no PHI cached" guarantee is structural (nothing from `/api` is cacheable) and
  test-enforced.
- One authored worker is easy to reason about and unit-test.

### Negative
- The worker needs the Workbox runtime libs (`workbox-precaching`/`-routing`/`-window`) as
  direct deps (pnpm strictness; the registration module imports `workbox-window`).
- A separate `tsconfig.worker.json` is extra config surface (the WebWorker and DOM libs can't
  share one project).

### Neutral
- Offline support is **app-shell-only** by decision — no cached reads, no offline writes.
  Offline data views show their existing error/empty state. Revisit only if offline data
  becomes a real need (it carries double-dose/sync risk for a medical app).
