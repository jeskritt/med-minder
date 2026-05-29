# Implementation Plan: Phase 8 — PWA Polish

**Branch**: `010-pwa-polish` | **Date**: 2026-05-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-pwa-polish/spec.md`

## Summary

Phase 8 turns the MedMinder frontend into an installable, offline-launchable PWA and polishes
the push experience that Phase 7 shipped in minimal form. Four slices:

1. **Installable PWA** — add `vite-plugin-pwa`, a web app manifest, a generated icon set
   (regular + maskable + apple-touch), theme/background colors, and real `index.html`
   metadata + title. Install is offered through the **browser's native affordance** plus a
   lightweight iOS "Add to Home Screen" hint (no custom `beforeinstallprompt` button).
2. **Offline app shell** — a Workbox-precached shell (built assets + an `index.html`
   navigation fallback) so the installed app launches offline and renders the shell with an
   offline indicator, instead of a browser error page. **No authenticated API data is ever
   cached** (privacy by default; FR-006).
3. **Polished push permission UX** — a contextual pre-prompt before the native permission
   dialog, per-state guidance for every `PushStatus` (incl. a denied→browser-settings
   recovery path), reusing the existing Phase 7 subscription flow unchanged.
4. **Notification actions** — "Snooze" (1h) and "Mark taken" buttons on dose-reminder
   notifications, handled in the service worker. Snooze reuses the existing
   `POST /reminders/{id}/snooze`; "Mark taken" calls a **new reminder-id-keyed endpoint**
   `POST /api/v1/reminders/{id}/take` that resolves the slot's attached medications and
   records a dose for **each**, **atomically** — if any dose hits a guard (the non-overridable
   overdose 409s or a drug-interaction cooldown) it records **nothing** and the SW shows a
   "open the app" follow-up notification (FR-015). Interaction cooldowns are **never**
   auto-acknowledged from a notification.

The only new **backend** surface is `POST /reminders/{id}/take` (reuses existing
`domain/doses.create_dose` + `domain/reminder_dispatch.resolve_dose_reminders`; **no schema
change**). The bulk of the work is **frontend/build**: the PWA plugin, an authored service
worker (`src/sw.ts`, injectManifest) that folds in the Phase 7 push/notificationclick logic
plus `notificationaction` handling, manifest + icons, an install hint, an offline indicator,
and the polished `EnableNotifications` flow. A new **ADR-0015** records the PWA/service-worker
strategy (FR-020), and the doc sweep updates `CLAUDE.md` and the diagrams.

## Technical Context

**Language/Version**: TypeScript ~6.0 (frontend), Python 3.13 (backend, one new endpoint)
**Primary Dependencies**: React 19, Vite 8, TanStack Router/Query, openapi-fetch (existing);
FastAPI + SQLAlchemy 2.0 async (existing) — **new pinned build deps**:
`vite-plugin-pwa` (Workbox-based SW + manifest generation) and `@vite-pwa/assets-generator`
(icon set from one source asset). No new **runtime** backend deps.
**Storage**: PostgreSQL 17 — **no migration, no new tables/columns**. The take endpoint reuses
`doses`, `reminders`, `schedule_medications`.
**Testing**: vitest + Testing Library + jsdom (components, install hint, offline indicator,
permission flow); a unit test asserting the SW precache manifest excludes `/api`; pytest +
httpx `AsyncClient` (the `take` endpoint, incl. take-all, guard fail-safe → atomic rollback,
cross-user 404); Playwright (E2E, skip-gated) extends `reminders.spec.ts` for the polished
enable flow. Lighthouse "installable" audit is a manual/CI-adjacent acceptance check (SC-002).
**Target Platform**: PWA — Android Chrome, iOS Safari 16.4+ (Web Push + installable), desktop
Chrome/Firefox.
**Project Type**: Web monorepo — `backend/` (FastAPI) + `frontend/` (Vite/React).
**Performance Goals**: installed app shell launches offline; precache covers the built shell;
no regression to first-load bundle budget (Phase 10 enforces Lighthouse/bundle budgets — this
phase must not block that).
**Constraints**: **No PHI in any cache** — the SW precaches only static build assets and the
navigation shell; `/api` is NetworkOnly, never cached (FR-006/SC-004; Principle I). Single
authored SW at `/sw.js` scope must **cleanly take over** the Phase 7 worker with no duplicate
push handlers and no infinite reload loop (FR-008/FR-009). Notification "Mark taken" is
**server-authoritative and atomic**, never bypasses an overdose guard, never auto-acknowledges
an interaction cooldown (FR-015/FR-016). Same-origin SW `fetch(credentials:'include')` carries
the `mm_session` cookie (SameSite=Lax, same-origin) — no new auth mechanism. New code is
`tsc --noEmit` / `mypy --strict` clean; coverage ≥85% with the 70% floor.
**Scale/Scope**: single-tenant; one installable client per device; a handful of icons; one new
endpoint.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Compliance plan |
|---|---|---|
| **I — Security-Conscious by Default (NON-NEGOTIABLE)** | **PASS** | **No PHI in caches**: the SW precaches only static shell assets and an `index.html` navigation fallback; `/api/*` is NetworkOnly and never cached (FR-006/SC-004) — a unit test asserts the generated precache manifest contains no `/api` entry. The new `POST /reminders/{id}/take` is **user-scoped** (reminder ownership check → 404 for others, mirroring snooze/dismiss `_load_owned_reminder`) with a cross-user negative test (FR-016). It **never auto-acknowledges** interaction cooldowns and **never bypasses** overdose guards; on any guard it rolls back atomically (FR-015). No new secrets (VAPID unchanged, private key still env-only); the manifest/icons carry no PII. New surface (one endpoint, manifest, SW) gets a "Security considerations" PR section and a `checklists/security.md` merge gate. |
| **II — Fully Typed Across the Stack** | **PASS** | The authored SW (`src/sw.ts`) is typed against the WebWorker lib in its own tsconfig include (`WorkerGlobalScope`/`workbox-*` types); the registration uses `virtual:pwa-register` typed via the `vite-plugin-pwa/client` reference. New components/hooks satisfy `tsc --noEmit` strict. The backend endpoint + any new Pydantic schema satisfy `mypy --strict`; OpenAPI stays the source of truth — `just generate-client` regenerates `frontend/src/api/v1.d.ts` for the new `take` endpoint and CI fails on drift (ADR-0003). Generated SW/manifest artifacts are excluded as generated. |
| **III — Loose Coupling, Testable Units** | **PASS** | The `take` endpoint is **thin transport** over the shared domain: it resolves the slot's meds, loops `domain/doses.create_dose` (same guards as the in-app take — no duplicated dosing logic), then `domain/reminder_dispatch.resolve_dose_reminders` (same resolution as in-app). No new domain duplication across CLI/web. Frontend: push subscription logic stays in `lib/push.ts`; the SW action handlers are small and call endpoints; the offline indicator and install hint are isolated presentational units, unit-tested without a real SW. |
| **IV — Documented Decisions** | **PASS** | **New ADR-0015** records the PWA/service-worker strategy: `vite-plugin-pwa` with **injectManifest** (to keep custom push handlers), app-shell-only precache, the rationale for **never caching API/PHI**, the SW-update flow (no reload loop), and SW-handled notification actions (FR-020). A sequence diagram for the notification-action flow (tap "Mark taken" → SW → `take` → guards/atomic → resolve / fail-safe notify) is added under `docs/diagrams/`. `er.md` is unchanged (no schema change). Full spec-kit artifact set lives in this folder. Doc sweep updates `CLAUDE.md` behavior notes. |
| **V — Cross-Platform Tooling Integrity** | **PASS** | New deps (`vite-plugin-pwa`, `@vite-pwa/assets-generator`) are **pinned with upper bounds**; the pnpm lockfile is committed; `pnpm audit` runs in CI. No new `scripts/` shell pair (icon generation runs via a pnpm script using the assets generator, not a `.sh`/`.ps1`). The new route added to `routeTree.gen.ts` is regenerated **on the host** (EXDEV in docker — see [[project_routetree_exdev_docker]]). CI pipeline (lint → typecheck → tests → OpenAPI drift → build) unchanged; the PWA build runs inside the existing `vite build`. |

**No violations.** Complexity Tracking section below is empty.

## Project Structure

### Documentation (this feature)

```text
specs/010-pwa-polish/
├── plan.md                      # This file
├── spec.md                      # Feature spec (/speckit-specify + /speckit-clarify)
├── research.md                  # Phase 0 — decisions R1–R9
├── data-model.md                # Phase 1 — no schema change; take endpoint data flow; cache policy
├── quickstart.md                # Phase 1 — baseline gate + per-story verification recipes
├── contracts/
│   └── pwa-polish.openapi.yaml  # Phase 1 — the one new endpoint (POST /reminders/{id}/take)
├── checklists/
│   ├── requirements.md          # Specify-stage merge gate (already green)
│   └── security.md              # NEW — no-PHI-in-cache, take-endpoint scoping/guards merge gate
└── tasks.md                     # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
frontend/
├── index.html                        # MODIFIED — title "MedMinder"; manifest link, theme-color, apple-touch-icon
├── vite.config.ts                    # MODIFIED — add VitePWA({ strategies:'injectManifest', srcDir:'src',
│                                      #            filename:'sw.ts', manifest:{...}, devOptions, workbox/injectManifest })
├── package.json                      # MODIFIED — pin vite-plugin-pwa + @vite-pwa/assets-generator; add "generate-pwa-assets" script
├── pwa-assets.config.ts              # NEW — icon preset (regular + maskable + apple-touch) from one source asset
├── public/
│   ├── medminder.svg                 # NEW — source brand asset for icon generation (and favicon)
│   ├── pwa-192x192.png .. 512 .. maskable .. apple-touch-icon.png  # GENERATED — committed icon set
│   └── sw.js                         # REMOVED — superseded by the built worker from src/sw.ts
├── src/
│   ├── sw.ts                         # NEW — authored SW (injectManifest): precacheAndRoute(self.__WB_MANIFEST) +
│   │                                 #        NavigationRoute(index fallback), NetworkOnly for /api, and the
│   │                                 #        Phase 7 push + notificationclick logic + NEW notificationclick action
│   │                                 #        handling (snooze/take via fetch(credentials:'include'))
│   ├── lib/
│   │   ├── push.ts                   # MODIFIED — stop hand-registering '/sw.js'; reuse the plugin-registered SW
│   │   └── pwa.ts                    # NEW — registerSW() wrapper (virtual:pwa-register) + update-available signal
│   ├── api/v1.d.ts                   # REGENERATED — adds POST /api/v1/reminders/{id}/take
│   ├── hooks/
│   │   └── usePushSubscription.ts    # MODIFIED (if needed) — unchanged contract; relies on plugin SW
│   ├── components/
│   │   ├── pwa/
│   │   │   ├── InstallHint.tsx       # NEW — iOS "Add to Home Screen" hint (dismissable; standalone-aware)
│   │   │   ├── OfflineIndicator.tsx  # NEW — navigator.onLine + online/offline events; small banner
│   │   │   └── UpdatePrompt.tsx      # NEW — "New version available — refresh" toast (no reload loop)
│   │   └── reminders/
│   │       └── EnableNotifications.tsx # MODIFIED — contextual pre-prompt + per-state guidance + denied recovery
│   ├── routes/__root.tsx             # MODIFIED — mount OfflineIndicator + InstallHint + UpdatePrompt in the shell
│   └── __tests__/
│       ├── EnableNotifications.test.tsx # MODIFIED — pre-prompt, denied guidance, unsupported, on/off
│       ├── OfflineIndicator.test.tsx    # NEW
│       ├── InstallHint.test.tsx         # NEW
│       └── sw-precache.test.ts          # NEW — asserts the precache manifest excludes /api (FR-006)
└── e2e/
    └── reminders.spec.ts             # MODIFIED (skip-gated) — polished enable flow assertions

backend/
├── src/medminder/
│   └── api/
│       └── reminders.py              # MODIFIED — add POST /{reminder_id}/take (atomic take-all + fail-safe)
└── tests/
    └── api/
        └── test_reminders_api.py     # MODIFIED — take: take-all records N doses + resolves; guard → 409 + nothing
                                      #            committed (atomic); idempotent when already resolved; cross-user 404

docs/
├── adr/
│   └── 0015-pwa-service-worker.md    # NEW — PWA/SW strategy (injectManifest, shell-only cache, no-PHI, actions)
├── diagrams/
│   ├── sequence-notification-action.md # NEW — Mermaid: tap "Mark taken" → SW → take → guards/atomic → resolve/fail-safe
│   └── README.md                     # MODIFIED — list the new diagram
└── (CLAUDE.md)                       # MODIFIED — Phase 8 behavior note + plan pointer (SPECKIT markers)
```

**Structure Decision**: Existing web-monorepo layout. Phase 8 is overwhelmingly frontend/build:
the PWA plugin and an **authored** service worker (`src/sw.ts`) via the injectManifest strategy
so the Phase 7 push handlers survive the migration (R1/R4). The single new backend endpoint
lands in the **existing** `api/reminders.py` next to snooze/dismiss and reuses the shared domain
functions — no new module, no migration. Icons are generated from one source asset and committed
(R7). The new route components live under `components/pwa/` and are mounted in the root shell.

## Implementation Phasing

Sequenced by spec priority (US1 → US2 → US3 → US4), with the PWA plugin landing first because
the shell, manifest, and SW underpin the rest.

- **Phase A — Baseline sanity gate (FIRST):** `python scripts/generate_openapi_client.py` and
  `cd backend && python -m alembic check` clean before any change; record current bundle size.
  (See `quickstart.md` Phase A.)
- **Phase B — PWA plugin + manifest + icons + shell** (US1, FR-001..004): add `vite-plugin-pwa`
  (injectManifest), author `src/sw.ts` (precache + navigation fallback + NetworkOnly `/api`,
  porting the Phase 7 push/notificationclick logic), remove `public/sw.js`, generate + commit
  the icon set, fill `index.html` (title/manifest/theme-color/apple-touch), wire `registerSW`.
- **Phase C — Offline shell + install hint + update prompt** (US3/US1, FR-005..008): mount
  `OfflineIndicator`, `InstallHint` (iOS), `UpdatePrompt` in `__root.tsx`; verify offline
  launch renders the shell and data views show a clear offline state (no stale data);
  `sw-precache.test.ts` proves `/api` is excluded.
- **Phase D — Polished push permission UX** (US2, FR-010..013): rework `EnableNotifications`
  (contextual pre-prompt, per-`PushStatus` guidance, denied→settings recovery); `push.ts` drops
  the manual `register('/sw.js')` and relies on the plugin-registered worker.
- **Phase E — Notification actions** (US4, FR-014..016): backend `POST /reminders/{id}/take`
  (atomic take-all + guard fail-safe), regenerate client; SW `notificationclick` action handling
  (`snooze` → existing endpoint, `take` → new endpoint, both `credentials:'include'`); on
  non-2xx, show a "open the app" follow-up notification; tap-body still opens `/reminders`.
- **Phase F — Cross-cutting** (FR-017..020): cross-user + guard-atomicity tests, no-PHI-in-cache
  test, ADR-0015, the sequence diagram, `checklists/security.md`, the doc sweep (`CLAUDE.md`),
  typing/lint/coverage gates, and a manual Lighthouse "installable" + real-device install check
  (SC-001/002).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

(no entries — all gates passed)
