# Phase 0 Research — Phase 8 (PWA Polish)

Engineering decisions resolving the unknowns `spec.md` deferred to `/speckit-plan`. The
user-facing forks (offline depth, notification actions, multi-med take, guard fail-safe,
install UX) were already settled in `spec.md` Clarifications; this file covers the *how*.
Format: **Decision / Rationale / Alternatives considered**.

---

## R1 — PWA tooling: `vite-plugin-pwa` with the **injectManifest** strategy

**Decision**: Add `vite-plugin-pwa` and use `strategies: 'injectManifest'` with an **authored**
service worker at `src/sw.ts` (output `sw.js` at the dist root). Workbox precaching is pulled in
via `precacheAndRoute(self.__WB_MANIFEST)`; the rest of the worker is our own code.

**Rationale**: The worker must host non-trivial custom logic that `generateSW` cannot express —
the Phase 7 `push` + `notificationclick` handlers and the new notification-**action** handling
(`snooze`/`take` via authenticated `fetch`). `injectManifest` is the documented path when you
need to own the SW source while still getting Workbox precaching/versioning. It also lets us
keep a **single** worker at the same `/sw.js` scope, so it cleanly supersedes the Phase 7 file
(R4) rather than running a second worker.

**Alternatives considered**: `generateSW` + `importScripts` for push logic (rejected — awkward
to thread custom action handling and a navigation fallback through generateSW's runtime-caching
config; injectManifest is the supported "custom SW" route). Hand-rolling a SW + manual Workbox
wiring without the plugin (rejected — loses manifest generation, dev-mode SW, and the typed
`virtual:pwa-register` registration; more bespoke code to maintain).

---

## R2 — Caching policy: app-shell precache only; `/api` is NetworkOnly (no PHI cached)

**Decision**: The SW **precaches only the static build output** (hashed JS/CSS/icons via
`self.__WB_MANIFEST`) plus a **NavigationRoute** that serves the precached `index.html` for
navigations when offline. **All `/api/*` requests are `NetworkOnly`** — there is no runtime
caching route for the API, so no authenticated/medical response is ever written to Cache
Storage. A `denylist` on the navigation route excludes `/api`.

**Rationale**: Directly satisfies the clarified **app-shell-only** scope and FR-006/SC-004
(no PHI in caches) — the privacy-safe default for an installed app on a possibly-shared device.
The shell renders offline; data views fail their fetch and show an offline state (R8) rather
than stale medical data.

**Alternatives considered**: StaleWhileRevalidate on `GET /api` reads (rejected — caches
medical data, violates the clarified scope and Principle I). Offline write queue / Background
Sync (rejected — explicitly out of scope; double-dose/conflict risk for a medical app).

---

## R3 — Service-worker update flow: prompt-to-refresh, no reload loop

**Decision**: Register via the plugin's `virtual:pwa-register` (`registerSW`) wrapped in
`src/lib/pwa.ts`, with an **update-available** callback that surfaces a small `UpdatePrompt`
("New version available — refresh") the user clicks to apply. `skipWaiting`/`clients.claim`
happen only on that explicit update, so a newly deployed shell is picked up on next launch/refresh
without an automatic reload loop (FR-008). `devOptions.enabled = true` so the SW is testable in
`vite dev`.

**Rationale**: A controlled prompt matches the spec edge case ("update applies on next launch,
or an explicit refresh-to-update affordance") and avoids the classic auto-`skipWaiting` reload
loop where an open client keeps reloading into a newer waiting worker.

**Alternatives considered**: `registerType: 'autoUpdate'` with auto-reload (rejected — reload-loop
risk and can interrupt the user mid-action). No update handling (rejected — risks a permanently
stuck stale shell, failing FR-008).

---

## R4 — Clean takeover from the Phase 7 `public/sw.js`

**Decision**: Delete `public/sw.js`; the built worker from `src/sw.ts` is emitted at the **same
`/sw.js` URL and root scope**, so an already-registered Phase 7 worker updates in place (same
scope = same registration) rather than producing a second worker. `lib/push.ts` stops calling
`navigator.serviceWorker.register('/sw.js')` and instead relies on the plugin's registration
(`registerSW`), still awaiting `navigator.serviceWorker.ready` before `pushManager.subscribe`.
The new worker carries the **same** `push`/`notificationclick` behavior plus the action handlers,
so there are no duplicate push handlers and no double notifications.

**Rationale**: Keeping the URL/scope stable is what makes the upgrade a clean in-place
replacement (FR-009). Centralizing registration in the plugin removes the double-registration
hazard of `push.ts` registering a worker the plugin also manages.

**Alternatives considered**: a new SW filename/scope (rejected — would leave the old `/sw.js`
registered and risk duplicate push delivery until it's unregistered).

---

## R5 — Notification "Mark taken": new reminder-id-keyed endpoint `POST /reminders/{id}/take`

**Decision**: Add `POST /api/v1/reminders/{reminder_id}/take`, in the existing
`api/reminders.py`, symmetric with snooze/dismiss. It:
1. Loads the caller-owned reminder via the existing `_load_owned_reminder` (→ 404 if not owned).
2. Resolves the **non-deleted medications attached to the reminder's `schedule_id`** (reusing
   the `ScheduleMedication`⋈`Schedule` non-deleted-join pattern from `domain/doses.py`).
3. Records a dose for **each** med via `domain/doses.create_dose(... taken_at=now,
   interaction_acknowledged=False)` — the **same guards** as the in-app take.
4. Calls `domain/reminder_dispatch.resolve_dose_reminders(... schedule_id, taken_at=now)` to
   mark the slot's open reminder(s) `dismissed`.

The SW already has `reminder_id` in the push payload, so **the payload is not expanded** with
medical ids (R6) — medical context stays server-side.

**Rationale**: Reminder-id-keyed is symmetric with the existing snooze/dismiss endpoints,
keeps medical context off the device, and centralizes guard handling + multi-med resolution in
one server call (the SW can't loop N requests reliably). Reuses the shared dosing domain — no
duplicated logic (Principle III).

**Alternatives considered**: extend the push payload with `schedule_id` + medication ids and
have the SW loop `POST /api/doses` (rejected — leaks medical context into the device-side
payload, and a per-med loop from a SW can't be atomic). A generic "act on reminder" endpoint
(rejected — snooze/dismiss already exist; an explicit `take` verb is clearer).

---

## R6 — `take` atomicity, guard handling, and HTTP semantics

**Decision**: The whole take runs in the request's single DB transaction and is **all-or-nothing**.
If **any** med's `create_dose` raises a guard error — `MinIntervalNotElapsedError`,
`WindowFullError`, `DailyCapReachedError` (non-overridable overdose 409s) or
`MedicationInteractionConflictError` (interaction cooldown) — the endpoint **does not commit any
dose** and returns **409** with the existing violation body (the first conflict). `interaction_acknowledged`
is **always `False`** here (no silent acknowledgment from a notification). Success returns
**204** (doses recorded + reminder dismissed). A reminder with no attached meds, or already
resolved, is an **idempotent 204** (nothing to do). Not the caller's reminder → **404**; refill
reminders (`type='refill'`, no `schedule_id`) → **409/422** (take is dose-only). The SW treats
any non-2xx as "couldn't record" → shows a follow-up "open the app" notification (FR-015).

**Mechanism (no new code)**: Atomicity and the 409 bodies are both provided by **existing**
infrastructure. `get_session` (`api/deps.py:29`) runs each request inside a single
`async with session.begin()` that commits on success and **rolls back on any exception** — so a
guard error mid-loop discards every dose already added. The four guard exceptions are converted
to their 409 violation bodies by **app-wide** `@app.exception_handler`s in `app.py:112-171`,
which apply to *any* route. The take endpoint therefore adds **no** exception handling and **no**
explicit commit; it only needs to let the guard exceptions propagate.

**Rationale**: Atomic fail-safe is exactly the clarified "records nothing on block" — predictable
from a no-UI notification context, and it preserves the informed-consent semantics of the in-app
interaction confirm (the user opens the app to acknowledge). 204 mirrors the existing dismiss
endpoint; reusing the existing violation schemas means no new error contract.

**Alternatives considered**: partial success (record the meds that pass, skip the blocked ones)
— rejected for the notification path: it's surprising with no UI to explain *which* med was
skipped, and contradicts the clarified "records nothing." Returning 200 with a tally — rejected
as needless surface; 204 + the existing 409 bodies suffice.

---

## R7 — Manifest, icons, and theme colors

**Decision**: Configure the manifest inline in `vite.config.ts` `VitePWA({ manifest: ... })`:
`name: "MedMinder"`, `short_name: "MedMinder"`, `description`, `start_url: "/"`, `scope: "/"`,
`display: "standalone"`, `theme_color: "#0f172a"` (slate-900), `background_color: "#f8fafc"`
(slate-50) — consistent with the existing UI palette. Generate the icon set with
`@vite-pwa/assets-generator` (`pwa-assets.config.ts`, `minimal-2023` preset) from a single source
`public/medminder.svg`: `pwa-192x192.png`, `pwa-512x512.png`, a **maskable** variant, and
`apple-touch-icon.png`; commit the generated PNGs. `index.html` gets `<title>MedMinder</title>`,
the manifest link (plugin-injected), `<meta name="theme-color">`, and `<link rel="apple-touch-icon">`.

**Rationale**: One source asset → a complete, consistent icon set (regular + maskable +
apple-touch) is the least-effort way to satisfy FR-001/003 and pass the Lighthouse installability
audit (SC-002). Committing the PNGs keeps the build deterministic and avoids a generator step in
CI's critical path.

**Alternatives considered**: hand-authoring each PNG (rejected — tedious, error-prone sizes).
Generating icons at build time only (rejected — non-deterministic CI, and the assets generator is
a dev tool better run intentionally via a pnpm script).

---

## R8 — Offline indicator + iOS install hint (no data caching)

**Decision**: `OfflineIndicator.tsx` tracks `navigator.onLine` + `online`/`offline` events and
renders a small banner in the root shell when offline. Data views need **no special offline
code** — TanStack Query fetches fail offline and the existing error/empty states show "data
unavailable"; the banner provides the global cue and a retry hint. **FR-007 verification**: "no
stale medical data" is *structural* — R2 caches nothing from `/api`, so a data view can only show
its live result or its (existing) error/empty state, never stale cache. It is checked by the
no-`/api`-cache test (T024) + the OfflineIndicator test (T020/T023) + a small data-view
offline-state test (`offline-data-view.test.tsx`, T023) + manual offline launch (T037).
`InstallHint.tsx` shows a
dismissable "Add to Home Screen" tip **only** on iOS Safari when not already in standalone mode
(`navigator.standalone` / `display-mode: standalone` check), since iOS has no programmatic
install prompt; Android/desktop rely on the browser's native install affordance (no custom
button).

**Rationale**: Satisfies US3 (clear offline state, no browser error page, no stale medical data)
and the clarified install UX (native + iOS hint) with minimal, isolated, unit-testable
components and zero API caching.

**Alternatives considered**: a custom `beforeinstallprompt` button on Android (rejected by the
clarification — native UI preferred). Caching last-fetched data for offline reads (rejected — out
of scope; PHI caching).

---

## R9 — Typing the service worker and registration

**Decision**: `src/sw.ts` is compiled by the plugin (esbuild) but type-checked with the
**WebWorker** lib: add a dedicated tsconfig include (or `/// <reference lib="webworker" />` +
`declare const self: ServiceWorkerGlobalScope`) and import Workbox types from the pinned
`workbox-*` packages the plugin pulls in. The registration wrapper imports the plugin's typed
virtual module via `/// <reference types="vite-plugin-pwa/client" />`. The `self.__WB_MANIFEST`
injection point is typed via the plugin's `vite-plugin-pwa/info` (or a local `declare`). Generated
artifacts (`dist/sw.js`, `dev-sw.js`) are git-ignored / excluded from `tsc`.

**Rationale**: Keeps the whole stack `tsc --noEmit` strict (Principle II) without leaking
worker globals into the app's DOM-typed code. The plugin ships first-class client types, so the
registration and virtual modules type cleanly.

**Alternatives considered**: untyped JS SW (rejected — violates Principle II's strict-TS bar).
A single tsconfig for app + worker (rejected — `WebWorker` and `DOM` libs conflict; the worker
needs its own lib set).

---

## Resolved unknowns checklist

| Spec-deferred item | Resolved by |
|---|---|
| Service-worker generation strategy (injectManifest vs generateSW) | R1 (injectManifest, authored `src/sw.ts`) |
| Offline caching strategy / scope | R2 (shell precache + navigation fallback; `/api` NetworkOnly) |
| SW update handling (no stale shell, no reload loop) | R3 (prompt-to-refresh via `virtual:pwa-register`) |
| Clean takeover from Phase 7 `sw.js` | R4 (same `/sw.js` scope; plugin owns registration) |
| Notification-action endpoint shape | R5 (`POST /reminders/{id}/take`, reminder-id-keyed) |
| Multi-med + guard-block + idempotency semantics | R6 (atomic take-all; 409 on any guard; 204 success/idempotent) |
| Manifest fields, icon set, theme colors | R7 (`@vite-pwa/assets-generator` from one source; slate palette) |
| Offline UX + install affordance | R8 (`OfflineIndicator` + iOS `InstallHint`; native install elsewhere) |
| SW + registration typing | R9 (WebWorker-lib tsconfig include; plugin client types) |
