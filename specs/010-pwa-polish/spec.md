# Feature Specification: PWA Polish

**Feature Branch**: `010-pwa-polish`

**Created**: 2026-05-29

**Status**: Draft

**Input**: User description: "@specs/roadmap.md phase 8"

## Clarifications

### Session 2026-05-29

- Q: How far should offline support go for the "offline app shell"? → A: **App shell
  only.** Cache the static shell (HTML/JS/CSS/icons) so the installed app launches offline
  and shows a clean offline state. **Authenticated API data is NOT cached** — no offline
  reads of medical data and no offline writes. This matches the roadmap's "offline app
  shell" wording and is the privacy-safe choice (no PHI persisted in the Cache Storage of an
  installed device).
- Q: Should Phase 8 add Snooze / Mark-as-taken action buttons directly on the push
  notification? → A: **Yes, include them.** Phase 7 explicitly deferred "notification-action
  buttons (acting while the app is closed)" to "Phase 8's polished push UX"; Phase 8 fulfils
  that. This implies a small authenticated surface the service worker can call to act on a
  reminder.
- Q: What happens to the existing hand-written `public/sw.js`? → A: It is **superseded by a
  build-tool-managed service worker** (vite-plugin-pwa) that **retains** the existing `push`
  and `notificationclick` handling — the custom logic is preserved, not discarded. The exact
  plugin strategy (injectManifest vs generateSW) is a `/speckit-plan` decision, not fixed
  here.
- Q: For a schedule slot with several attached medications, what does the notification "Mark
  taken" action record? → A: It records a dose for **every** medication attached to that slot
  (mirroring the in-app "Take all", which loops one dose per medication) and then resolves
  the reminder. There is no atomic "take all" at the API level today; the take action records
  each medication's dose.
- Q: What happens when a notification "Mark taken" is blocked by a dose guard (no confirm UI
  is available from a notification)? → A: **Fail safe.** If recording is blocked by a
  non-overridable overdose guard (min-interval, window-full, or daily-cap — all 409) or by a
  drug-interaction cooldown, the action records nothing and surfaces a follow-up notification
  telling the user to open the app. Overdose guards stay enforced and interaction cooldowns
  are **never silently acknowledged** from a notification — the informed
  `interaction_acknowledged` override happens only in-app.
- Q: How does the service worker carry out a take, given the push payload holds only
  `reminder_id`/`type`/`title`? → A: Via a **new reminder-id-keyed endpoint** (`POST
  /reminders/{id}/take`), symmetric with the existing `POST /reminders/{id}/snooze` and
  `/dismiss`, that resolves the slot's medications and runs the guards server-side. The
  service worker only needs `reminder_id` (already in the payload); the push payload is **not**
  expanded with medication/schedule ids, keeping medical context off the device.
- Q: How is installation offered, given iOS Safari has no programmatic install prompt? → A:
  Rely on the **browser's native install affordance** plus a lightweight iOS "Add to Home
  Screen" hint. No custom `beforeinstallprompt`-driven install button.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Install MedMinder as an app (Priority: P1)

A user opens MedMinder in a mobile browser and installs it to the home screen; it launches
standalone (no browser chrome) with the correct name, icon, and theme color.

**Why this priority**: Being installable is the defining capability of "PWA polish" and an
explicit roadmap exit criterion ("Verified installable on iOS Safari and Android Chrome").
It is the smallest independently shippable and demonstrable slice of the phase.

**Independent Test**: On Android Chrome, the browser's native install affordance is offered
and "Add to Home Screen" produces a standalone app with MedMinder's icon and name; on iOS
Safari, the in-app "Add to Home Screen" hint guides the user through the Share-menu install,
and the app opens full-screen.

**Acceptance Scenarios**:

1. **Given** a supported browser, **When** the user visits the app, **Then** a valid web app
   manifest (name, short_name, icons, theme_color, background_color, display=standalone,
   start_url) is served and recognized by the browser, and installation is offered through
   the browser's native affordance (no custom in-app install prompt; iOS shows a lightweight
   "Add to Home Screen" hint).
2. **Given** the app is installed, **When** it is launched from the home screen, **Then** it
   opens full-screen/standalone with the branded icon and theme color, not as a browser tab.
3. **Given** an installed icon, **When** viewed on the home screen at the platform's required
   sizes, **Then** a crisp icon (including a maskable variant) is shown — no default or blank
   glyph.

---

### User Story 2 — Understand and enable notifications without confusion (Priority: P2)

Before the browser's native permission dialog appears, the user sees a plain-language
explanation of what reminders do and why; if they have previously blocked notifications,
they get clear guidance instead of a dead button.

**Why this priority**: Push is the core value of the reminders feature; a confusing or
silent permission flow loses users at the highest-intent moment. It builds on Phase 7's
already-working subscription code, so it is polish rather than new plumbing.

**Independent Test**: From the default state, the enable flow shows a contextual pre-prompt;
on accept, the native dialog appears and the device subscribes. From the denied state, the
UI explains how to re-enable in browser settings rather than failing silently.

**Acceptance Scenarios**:

1. **Given** permission is "default", **When** the user starts enabling, **Then** a
   contextual explanation precedes the native OS prompt (no surprise dialog).
2. **Given** the user accepts, **When** subscription completes, **Then** the device registers
   a subscription and the UI clearly reflects the enabled state for *this* device.
3. **Given** permission is "denied", **When** the user views the notifications control,
   **Then** the UI explains notifications are blocked and how to re-enable them in browser
   settings (it does not show a button that cannot work).
4. **Given** the browser does not support push, **When** the user views the control, **Then**
   the UI says so and reassures that reminders still appear in-app.
5. **Given** an enabled device, **When** the user turns notifications off, **Then** the
   subscription is removed and the state updates.

---

### User Story 3 — Launch offline without a browser error (Priority: P2)

A user who opens the installed app with no connection sees the MedMinder shell and a clear
"you're offline" indication, not the browser's error page.

**Why this priority**: An installed app that white-screens offline feels broken; the app
shell is the baseline PWA expectation. Scoped to shell-only (no cached medical data), it is
contained and independently testable.

**Independent Test**: Install the app, go offline, relaunch → the app shell renders with an
offline indicator; data-dependent views show an offline empty/error state rather than a
crash.

**Acceptance Scenarios**:

1. **Given** the app shell assets are cached, **When** the device is offline and the app is
   launched, **Then** the shell (layout, nav, branding) renders instead of a browser error
   page.
2. **Given** the device is offline, **When** a data view is opened, **Then** it shows a clear
   offline state (data unavailable) — it does not display stale cached medical data and does
   not hard-crash.
3. **Given** the device regains connectivity, **When** the user retries, **Then** live data
   loads normally.
4. **Given** a new app version is deployed, **When** the user next launches, **Then** the
   updated shell is picked up (no permanently stuck stale shell).

---

### User Story 4 — Act on a reminder from the notification (Priority: P3)

A user receiving a dose-reminder notification can Snooze it for an hour or mark the dose
taken directly from the notification's action buttons, without opening the app.

**Why this priority**: Fulfils Phase 7's deferred notification-action UX and removes
friction, but the loop already works via "tap to open"; sequenced last.

**Independent Test**: Trigger a dose reminder; with the app closed, tap the notification's
"Snooze" → the reminder re-fires ~1h later; tap "Mark taken" → the dose is recorded and the
reminder resolves.

**Acceptance Scenarios**:

1. **Given** a dose-reminder notification, **When** the user taps "Snooze", **Then** the
   reminder is snoozed for one hour (same behavior as the in-app snooze) without opening the
   app.
2. **Given** a dose-reminder notification, **When** the user taps "Mark taken", **Then** a
   dose is recorded for **each** medication attached to the reminder's schedule slot and the
   reminder is resolved.
3. **Given** a notification, **When** the user taps the notification body (not an action),
   **Then** the app opens to the reminders view (existing Phase 7 behavior preserved).
4. **Given** an action is taken on a reminder that no longer applies (already taken or
   dismissed), **When** the action runs, **Then** it is idempotent and surfaces no error.
5. **Given** any notification action, **When** it runs, **Then** it acts only on the
   recipient user's own reminder.
6. **Given** "Mark taken" would be blocked by a dose guard (a non-overridable overdose guard,
   or a drug-interaction cooldown), **When** the user taps it, **Then** no dose is recorded
   and a follow-up notification tells the user to open the app — overdose guards stay enforced
   and interaction cooldowns are never silently acknowledged from the notification.

### Edge Cases

- **iOS Safari limitations** — install/push are only available from an installed PWA and
  action-button support is limited; the flow degrades gracefully (tap-to-open still works)
  without errors.
- **Missing icon size** — if a required icon size is absent, installability checks would
  fail; the full required icon set (including a maskable icon) must be provided.
- **Service-worker update while a client is open** — no infinite reload loop; the update
  applies on next launch (or via an explicit "refresh to update" affordance).
- **Offline launch before the worker has ever cached the shell** (first visit was online but
  the worker had not yet activated) — falls back to a normal online load; no crash.
- **Notification action fired with an expired session** — the action fails closed (rejected,
  no cross-user effect); the user is not silently placed into a wrong state.
- **"Mark taken" blocked by a dose guard** (overdose 409 or interaction cooldown) — fails
  safe: nothing is recorded and a follow-up notification directs the user to open the app to
  resolve it; the notification action never bypasses an overdose guard or auto-acknowledges
  an interaction conflict.
- **Replacing the existing service worker** — must not orphan an already-registered Phase 7
  worker; clean takeover, with no duplicate push handlers / double notifications.

## Requirements *(mandatory)*

### Functional Requirements

#### Installability & manifest (US1)

- **FR-001**: The app MUST serve a valid web app manifest including at least name,
  short_name, description, start_url, scope, display=standalone, theme_color,
  background_color, and a complete icon set with maskable icons at platform-required sizes.
- **FR-002**: The app's HTML document MUST reference the manifest and include theme-color and
  apple-touch-icon metadata, and the document title MUST be the product name ("MedMinder"),
  not the placeholder "frontend". Installation MUST be offered through the browser's native
  install affordance (no custom `beforeinstallprompt`-driven button); on iOS Safari, which
  has no programmatic prompt, the app MUST show a lightweight "Add to Home Screen" hint.
- **FR-003**: A branded icon set (regular and maskable) MUST be provided, sufficient for
  Android Chrome and iOS Safari home-screen installation.
- **FR-004**: The build MUST integrate a PWA tooling pipeline that generates and serves the
  service worker and manifest as part of the production build; any added dependency MUST be
  pinned and reviewed per the constitution.

#### Service worker & offline app shell (US3)

- **FR-005**: A service worker MUST precache the static app shell (HTML/JS/CSS/icons) so the
  app launches offline and renders the shell instead of a browser error page.
- **FR-006**: The service worker MUST NOT cache authenticated API responses — no
  medical/dose/medication data is persisted to the cache (app-shell-only scope; privacy by
  default).
- **FR-007**: When offline, data-dependent views MUST show a clear offline state and MUST NOT
  display stale medical data; on reconnect, live data MUST load normally.
- **FR-008**: The service worker MUST support clean updates: a newly deployed shell is picked
  up on next launch with no stuck stale shell and no infinite reload loop.
- **FR-009**: The build-managed worker MUST retain the existing Phase 7 `push` and
  `notificationclick` handling; replacing the current hand-written worker MUST cleanly take
  over from any previously registered worker without producing duplicate notifications.

#### Push permission UX (US2)

- **FR-010**: Before invoking the browser's native permission prompt, the app MUST present a
  plain-language explanation of reminders and what enabling does.
- **FR-011**: The UI MUST clearly reflect each push state — supported/unsupported, default,
  granted+subscribed, granted+unsubscribed, denied — and provide the appropriate action or
  guidance for each, including how to re-enable from the denied/blocked state in browser
  settings.
- **FR-012**: Enabling MUST reuse the existing Phase 7 subscription flow (request permission
  → register the worker → fetch the VAPID public key → subscribe → register the
  subscription), and disabling MUST remove the subscription; no change to the existing
  subscription API contract is required.
- **FR-013**: When push is unavailable or denied, the app MUST reassure the user that
  reminders remain visible in-app (the in-app list is the always-on fallback).

#### Notification actions (US4)

- **FR-014**: Dose-reminder notifications MUST offer "Snooze" (one hour) and "Mark taken"
  action buttons handled by the service worker so the user can act without opening the app;
  tapping the notification body MUST continue to open the app (Phase 7 behavior preserved).
- **FR-015**: The "Snooze" action MUST produce the same one-hour snooze as the in-app
  control; the "Mark taken" action MUST record a dose for **every** medication attached to the
  reminder's schedule slot and resolve the reminder. Both MUST be idempotent if the reminder
  no longer applies. If recording is blocked by a dose guard — a non-overridable overdose
  guard (min-interval, window-full, or daily-cap) or a drug-interaction cooldown — the action
  MUST fail safe: record nothing and surface a follow-up notification directing the user to
  open the app. The notification action MUST NOT bypass an overdose guard and MUST NOT
  auto-acknowledge an interaction cooldown (the informed acknowledgment is in-app only).
- **FR-016**: Notification actions MUST be carried out through **reminder-id-keyed endpoints**
  — reusing the existing snooze/dismiss endpoints and adding a take endpoint (`POST
  /reminders/{id}/take`) that resolves the slot's medications and runs the guards
  server-side — so the push payload is **not** expanded with medication/schedule ids and
  medical context stays off the device. Every action MUST be authenticated and scoped to the
  recipient user, MUST never affect another user's reminders, and MUST fail closed if the
  session is invalid.

#### Cross-cutting (security, typing, coverage, docs)

- **FR-017** (security): New surfaces (any notification-action endpoint, manifest/worker
  configuration) MUST be reviewed — user-scoped authorization on actions, no PHI in caches,
  push/VAPID secrets unchanged and never exposed, and service-worker scope limited to the app
  origin.
- **FR-018** (typing): New backend code MUST satisfy `mypy --strict`; new frontend code MUST
  satisfy `tsc --noEmit` strict (generated worker/manifest artifacts excluded as generated).
- **FR-019** (coverage): Project coverage MUST stay ≥85% with no module below the 70% floor.
- **FR-020** (docs): A new ADR MUST record the PWA/service-worker strategy (build-tool-managed
  worker, app-shell-only caching, the rationale for not caching API/PHI data, and
  service-worker-handled notification actions). A documentation sweep MUST update CLAUDE.md
  behavior notes and any affected diagrams/contracts; if a notification-action endpoint is
  added, the OpenAPI contract and generated client MUST be regenerated.

### Key Entities

- **PushSubscription** *(existing)*: a device endpoint + keys, unique per (user, endpoint);
  reused unchanged — enablement still creates it and disabling removes it.
- **Reminder** *(existing)*: notification actions act on dose reminders (snooze / resolve);
  no new columns anticipated.
- **Web App Manifest / Service Worker** *(new build artifacts)*: generated by the PWA
  pipeline; not database entities.
- **No new persistence anticipated**: the new reminder-id-keyed take endpoint (`POST
  /reminders/{id}/take`) reuses the existing reminder and dose tables (no schema change).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The app is verified installable on **both** Android Chrome and iOS Safari,
  opening standalone with the correct name, icon, and theme color.
- **SC-002**: An automated PWA/installability audit (e.g. a Lighthouse "installable" check)
  passes — valid manifest, registered service worker, and required icons present.
- **SC-003**: Launching the installed app **offline** renders the app shell (not a browser
  error page) 100% of the time after the first successful online load.
- **SC-004**: No authenticated API or medical data is present in the service worker caches
  (verified by inspection/test).
- **SC-005**: From the default state, a user can enable notifications via the guided flow and
  the device receives a test push; from the denied state the UI shows recovery guidance
  rather than a non-functional button.
- **SC-006**: A user can Snooze (1h) and Mark-as-taken a dose reminder directly from the
  notification with the app closed; "Mark taken" records a dose for every medication in the
  slot and resolves the reminder (same result as the in-app actions), acts only on their own
  reminders, and when a dose guard would block it, records nothing and notifies the user to
  open the app.
- **SC-007**: A newly deployed shell is picked up on next launch with no stuck stale shell
  and no reload loop.

## Assumptions

- The Phase 7 push infrastructure (subscription endpoints, VAPID public-key serving, the
  `push_subscriptions` table, and the dispatch loop) is reused as-is; Phase 8 is
  client/worker/manifest polish plus a small reminder-id-keyed take endpoint that reuses
  existing tables — no `push_subscriptions` or `reminders` schema change is anticipated.
- The hand-written `public/sw.js` is replaced by a build-tool-managed worker that keeps the
  existing push/notificationclick logic; the exact plugin strategy (injectManifest vs
  generateSW) is a `/speckit-plan` decision.
- Offline support is **app-shell-only** by decision; cached read data and offline writes are
  explicitly out of scope for this phase.
- iOS Safari's PWA limitations (install required for push, limited action-button support) are
  accepted; the flow degrades gracefully.
- Branding (theme/background color) follows the existing UI palette (slate); a source icon
  asset exists or can be provided to generate the icon set.
- Verification of installability on real iOS and Android devices is a manual acceptance step;
  the automated suite covers the manifest/worker/installability audit and notification-action
  behavior.

## Dependencies

- Phase 7 (008) — push delivery, the frontend push library and hooks, the existing "Enable
  notifications" control, the reminder dispatch loop, and the snooze/dismiss + dose-recording
  paths reused by notification actions.
- Phase 4/5 — dose recording (the `create_dose` path) reused by "Mark taken".
- The Vite build pipeline and the OpenAPI → TypeScript client generation (the new
  `POST /reminders/{id}/take` endpoint requires regenerating the client).
- New runtime/build dependency: a Vite PWA plugin (and Workbox), pinned and reviewed per the
  constitution.
