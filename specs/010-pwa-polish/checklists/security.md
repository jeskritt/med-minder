# Security Checklist: PWA Polish

**Purpose**: Security merge gate for this phase's new surface — the service worker / caching
policy and the one new endpoint (`POST /reminders/{id}/take`) (Constitution Principle I).
Every item must be `[x]` (verified) or `[~]` (PR/CI-runtime, with a link) before merge.
**Created**: 2026-05-29
**Feature**: [spec.md](../spec.md) · Decision: [ADR-0015](../../../docs/adr/0015-pwa-service-worker.md)

## No PHI in caches (FR-006 / SC-004)

- [x] The service worker precaches only static shell assets (`__WB_MANIFEST` from a
  static-extension `globPatterns`); `/api` has no runtime caching route and is denylisted from
  the navigation fallback — `frontend/src/__tests__/sw-precache.test.ts`.
- [x] No medical/dose/medication response can be written to Cache Storage — there is no
  `CacheFirst`/`StaleWhileRevalidate`/`NetworkFirst` strategy anywhere in `src/sw.ts`
  (asserted by the same test).
- [x] Offline data views show their error/empty state, never stale cached data —
  `frontend/src/__tests__/offline-data-view.test.tsx`.

## Authentication & authorization (FR-016)

- [x] `POST /reminders/{id}/take` requires an authenticated session (inherits
  `get_current_user`); a reminder that isn't the caller's is **404**, never acted on —
  `tests/api/test_reminders_api.py::test_take_cross_user_is_404`.
- [~] Service-worker actions call same-origin endpoints with `credentials: "include"`, so the
  `mm_session` cookie (HTTP-only, SameSite=Lax) authenticates them; an expired session fails
  closed (non-2xx → the SW shows an "open the app" notice, records nothing) — verified at
  PR/manual review of `src/sw.ts` `actOnReminder`.

## Overdose guards & no silent acknowledgment (FR-015)

- [x] A blocked take records nothing: any overdose guard (min-interval / window-full /
  daily-cap) returns **409** with no dose written and the reminder left unresolved —
  `tests/api/test_reminders_api.py::test_take_blocked_by_a_guard_records_nothing`.
- [x] `take_reminder` always passes `interaction_acknowledged=False` — an interaction cooldown
  is **never** silently acknowledged from a notification; the informed override stays in-app
  (`domain/doses.py::take_reminder`).
- [x] The take is atomic — `create_dose` validates guards before inserting, and the request
  transaction (`get_session`) rolls back the whole slot on any guard error, so a multi-med
  slot never partially records (`domain/doses.py`; ADR-0015).

## Secret handling & data minimization

- [x] No new secrets: VAPID keys are unchanged from Phase 7 (private key env-only, never
  exposed). The new endpoint adds no secret surface.
- [x] The push payload is **not** expanded with medication/schedule ids — medical context
  stays server-side; the SW acts only with the `reminder_id` it already receives
  (`src/sw.ts`, `domain/reminder_dispatch.py` payload unchanged).
- [x] No new database columns or tables; the manifest/icons carry no user data.

## Service-worker scope

- [x] The worker is served at `/sw.js` (origin root) with default scope; it replaces the
  Phase 7 worker in place (no duplicate push handlers / double notifications) and registers
  no cross-origin routes (`src/sw.ts`, `vite.config.ts`).
