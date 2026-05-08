# Quickstart: mark-as-taken

## What ships in this phase

- **No `doses` migration** — that table already exists from Phase 1a.
- **One new migration** for the `dose_voids` table.
- New backend endpoints: `POST /api/doses`, `POST /api/doses/{id}/void`,
  `GET /api/schedules/today`.
- A frontend Today route, a `MarkAsTaken` toggle, and an undo
  confirmation modal.
- The repo's first Playwright E2E smoke.

## Development setup

1. **Database migration** — add the `dose_voids` table.

   ```bash
   just generate-migration "add_dose_voids_table"
   just migrate
   ```

   Hand-check the generated revision before committing: `dose_id`
   needs `UNIQUE` and FK to `doses.id` with `ondelete=RESTRICT`.

2. **Regenerate the typed API client** after wiring the new endpoints:

   ```bash
   just generate-client
   ```

3. **Playwright** (first install in this repo):

   ```bash
   cd frontend
   pnpm install -D @playwright/test
   pnpm dlx playwright install chromium
   ```

   Then run the smoke:

   ```bash
   pnpm test:e2e
   ```

## Manual verification flow

1. `medminder-admin user add ...` to create a test user (Phase 1b CLI).
2. Log in via the Phase 2 login page.
3. Create a medication with `times_per_day=2` and attach it to two
   schedules (`08:00` and `20:00`).
4. Open `/today`. Both slots should appear, ordered by time.
5. Click "Taken" on the morning slot. The row greys out immediately
   (optimistic UI). Network tab shows `POST /api/doses` with
   `schedule_id` set.
6. Click the now-greyed row. The confirmation modal appears with the
   text from FR-005.
7. Confirm. The slot returns to "untaken." Network tab shows
   `POST /api/doses/{id}/void` returning `204`.
8. Refresh — server state matches the UI.

## Reference

- Schema (existing + new): `specs/004-mark-as-taken/data-model.md`.
- Endpoints: `specs/004-mark-as-taken/contracts/api.md`.
- Phase 1a `doses` definition:
  `specs/2026-04-29-phase-1-data-model/requirements.md` §"doses".
