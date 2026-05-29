# Quickstart — Phase 8 (PWA Polish)

Kickoff gate + per-story verification recipes. Commands assume the dev stack
(`just dev`) and are run from the repo root unless noted. `just` recipes use bash (Git
Bash/WSL on Windows).

## Phase A — Baseline sanity gate (run FIRST, before any change)

So later drift is unambiguously Phase 8's:

```bash
python scripts/generate_openapi_client.py     # client matches runtime spec (no drift)
cd backend && python -m alembic check && cd .. # no pending migration (and none will be added)
cd frontend && pnpm build                      # record current dist bundle size for comparison
```

Note the current bundle size; Phase 8 must not blow the budget Phase 10 will enforce.

> ⚠️ Serialize DB-touching commands — never run `alembic`/CLI concurrently against dev
> Postgres (see [[feedback_serialize_db_processes]]). Phase 8 adds **no** migration, so
> `alembic check` should stay clean throughout.

## Phase B — Installable PWA (US1)

After adding `vite-plugin-pwa`, the manifest, the icon set, and `index.html` metadata:

```bash
cd frontend && pnpm build && pnpm preview   # serve the production build (SW only fully works on a build)
```

- The document title is **"MedMinder"** (not "frontend").
- DevTools → Application → **Manifest**: name/short_name/theme_color/background_color/icons all
  present; "installable" with no errors.
- DevTools → Application → **Service Workers**: one worker registered at `/sw.js`, activated.
- Icons (192/512 + maskable + apple-touch) load; the maskable icon previews correctly.
- **Lighthouse** (Application/PWA): the **installable** audit passes (SC-002).
- Manual (SC-001): on Android Chrome the native install affordance appears and "Add to Home
  Screen" launches standalone with the MedMinder icon; on iOS Safari the in-app hint guides the
  Share-menu install and the app opens full-screen.

## Phase C — Offline app shell (US3)

```bash
cd frontend && pnpm preview
```

- Load the app once online (lets the SW precache the shell).
- DevTools → Network → **Offline**, then reload: the **app shell renders** (nav/branding) with
  the **OfflineIndicator** banner — not the browser error page (FR-005).
- Open a data view while offline: it shows a clear **offline/unavailable** state, **no stale
  medical data**, no crash (FR-007). Go back online → data loads.
- Deploy a new build, relaunch: the **UpdatePrompt** offers a refresh; applying it loads the new
  shell with **no reload loop** (FR-008).
- Test: `cd frontend && pnpm test -- sw-precache.test.ts` — the precache manifest contains **no
  `/api`** entries (FR-006/SC-004).

## Phase D — Polished push permission UX (US2)

On `/reminders`, exercise each `PushStatus` (DevTools can reset notification permission per
origin):

- **default** → starting "Enable notifications" shows the **contextual pre-prompt** before the
  native OS dialog; accepting subscribes the device and the UI shows the **enabled** state.
- **denied** → the control explains notifications are blocked and how to re-enable in browser
  settings (no dead button) (FR-011).
- **unsupported** → a message that the browser lacks support, reassuring that reminders still
  appear in-app (FR-013).
- **subscribed** → "Turn off" removes the subscription and the state updates.

```bash
cd frontend && pnpm test -- EnableNotifications.test.tsx
```

## Phase E — Notification actions (US4)

Backend first:

```bash
cd backend && python -m pytest tests/api/test_reminders_api.py -k take -v
```

- **take-all**: a slot with N attached meds records **N** doses and resolves the reminder (204).
- **guard fail-safe (atomic)**: if any med trips a guard (e.g. a `multi_sub_dose` window-full or
  an interaction cooldown), the call returns **409** and **no dose row** is written (verify the
  dose count is unchanged) and the reminder stays open (FR-015).
- **idempotent**: taking an already-resolved reminder (or one with no meds) → 204, no-op.
- **cross-user**: another user's reminder → **404** (FR-016).

Then regenerate the client and exercise the SW path:

```bash
python scripts/generate_openapi_client.py   # adds POST /api/v1/reminders/{id}/take to v1.d.ts
cd backend && python -m alembic check        # still clean (no migration)
```

Manual (SC-006), with notifications enabled and a dose reminder delivered (app closed):
- Tap **Snooze** → reminder re-fires ~1h later (reuses `snooze`).
- Tap **Mark taken** → doses recorded for the slot, reminder resolves; tapping a reminder whose
  take is guard-blocked yields a **follow-up "open the app" notification** and nothing recorded.
- Tap the **notification body** (not an action) → app opens to `/reminders` (Phase 7 behavior).

## Phase F — Cross-cutting gates (FR-017..020)

```bash
just lint          # ruff + eslint + prettier --check
just typecheck     # mypy --strict + tsc --noEmit (incl. the worker tsconfig)
just test          # backend (pytest, coverage ≥85%) + frontend (vitest)
cd frontend && pnpm audit    # no un-triaged high-severity in the new deps
```

- **Security**: `checklists/security.md` green — no PHI in caches (test), `take` endpoint
  user-scoped + atomic + never auto-acknowledges interactions, VAPID secrets untouched.
- **Docs**: ADR-0015 written; `docs/diagrams/sequence-notification-action.md` added and listed in
  `docs/diagrams/README.md`; `CLAUDE.md` Phase 8 behavior note + plan pointer updated.
- **Route regen**: after adding any route/component that affects routing, regenerate
  `routeTree.gen.ts` **on the host** (EXDEV under docker — see [[project_routetree_exdev_docker]])
  and re-run `tsc`.

## Definition of done (maps to Success Criteria)

| Check | Criterion |
|---|---|
| Installable on Android Chrome + iOS Safari, standalone w/ icon+theme | SC-001 |
| Lighthouse "installable" audit passes | SC-002 |
| Offline launch renders the shell, not a browser error | SC-003 |
| No `/api`/medical data in SW caches (test) | SC-004 |
| Guided enable works; denied shows recovery, not a dead button | SC-005 |
| Snooze + Mark-taken from the notification (take-all + fail-safe), own reminders only | SC-006 |
| New shell picked up on next launch; no stuck stale shell / reload loop | SC-007 |
