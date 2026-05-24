# Quickstart — Phase 7 (Reminders + Snooze)

How to bring the stack up, configure push, and verify each user story end-to-end. Commands
assume the repo root; `just` recipes need Git Bash/WSL on Windows (PowerShell-direct
equivalents are given where it matters).

## Phase A — Baseline sanity gate (run FIRST, before any Phase 7 change)

So any later drift is unambiguously Phase 7's:

```bash
# OpenAPI client is in sync with the backend
python scripts/generate_openapi_client.py        # (or: just generate-client)
git diff --exit-code frontend/src/api/v1.d.ts     # must be clean

# Migrations match the models
cd backend && python -m alembic upgrade head && python -m alembic check   # must report no drift
```

Re-run both after adding `0006_reminder_indexes.py` and the new routers/schemas.

## One-time push configuration

Web Push needs a stable VAPID key pair. Generate one and put it in the backend env
(`.env` / Docker compose / secret store):

```bash
python scripts/generate_vapid_keys.py
# prints VAPID_PUBLIC_KEY=..., VAPID_PRIVATE_KEY=..., suggested VAPID_SUBJECT=mailto:you@example.com
```

```dotenv
# backend env
VAPID_PUBLIC_KEY=<public>
VAPID_PRIVATE_KEY=<private>     # secret — never commit, never log
VAPID_SUBJECT=mailto:you@example.com
REMINDERS_ENABLED=true          # default true in app; tests/CI run with false
```

If the keys are left empty (e.g. local poke-around), reminders are still generated and visible
in-app; push sends are skipped. Tests and CI run with `REMINDERS_ENABLED=false` so no
background scheduler races the rollback fixture.

Bring the stack up:

```bash
just dev        # Postgres 17 + backend (:8000) + frontend (:5173)
```

Create a user and a schedule with at least one attached medication (admin CLI + the app), then
sign in.

## Per-user-story verification

### US1 — Get a push reminder when a scheduled dose is due (P1)

1. On the **Reminders** page, click **Enable notifications**; accept the browser permission.
   Confirm a subscription was registered (`POST /api/v1/push/subscriptions` → 201).
2. Create/edit a schedule so a slot's time is ~1 minute out, with a med attached.
3. Within a tick (≤30s of the slot), the device shows a Web Push notification naming the
   medication(s); `GET /api/v1/reminders` shows the row flip `pending → sent`.
4. **No-subscription**: with notifications disabled, the same slot still appears in
   `GET /api/v1/reminders` (in-app) and no send is attempted / no error.
5. **Restart**: `just dev-down && just dev`; pending reminders still fire (they live in the
   `reminders` table, not an in-memory job).

### US2 — Snooze a reminder for an hour (P2)

1. With a visible reminder, click **Snooze** in the in-app list.
2. The original row shows `snoozed`; a new `pending` row appears at `now + 1h`
   (`POST /api/v1/reminders/{id}/snooze` returns the new reminder).
3. Snooze again when it fires → re-snoozed another hour (no cap).
4. Snoozing another user's reminder id → **404** (cross-user, FR-017).

### US3 — Respect quiet hours (P2)

1. Set the user's quiet hours to a window containing the slot time, e.g.
   `medminder-admin user update --email <e> --quiet-hours-start 22:00 --quiet-hours-end 07:00`
   (admin-managed like `timezone`; backend tests may set the columns via a fixture instead).
2. At the slot time inside the window: no push fires; the reminder's `scheduled_for` is moved
   to the window end and stays `pending`.
3. At the window end: it fires. Verify the **midnight-wrap** case (02:00 → deferred to 07:00).
4. Clear quiet hours → reminders fire immediately again.

### US4 — Reminders follow schedule edits (P2)

1. With reminders generated for a schedule, change its time/days → future `pending` dose
   reminders for that schedule are regenerated to the new time; stale ones are gone.
2. Delete the schedule → its future `pending` reminders are cancelled.
3. Attach a new med / detach a med → generation follows. After any mutation,
   `GET /api/v1/reminders` matches the current schedule state (no stale/missing rows, SC-005).
   Past `sent`/`dismissed` rows are untouched.

### US5 — Refill warning on live supply (P2)

1. Set a med's `refill_count` just above `refill_threshold`. Take doses → `refill_count`
   decrements by one each take (floored at zero; a take at zero still succeeds).
2. When a take brings `refill_count` ≤ `refill_threshold`, a `refill` reminder is generated
   naming the med and remaining count. Take again while still at/below threshold → **no
   duplicate** warning.
3. Void a dose → `refill_count` restores by one.
4. Edit the med to raise `refill_count` back above `refill_threshold` → the open refill warning
   resolves; a later crossing can warn again.
5. A med with `refill_threshold` unset never warns (opt-in).

### US6 — Resilient delivery (P3)

1. Register a subscription, then make its endpoint invalid (or use a test that mocks a 410).
   On the next fire, the subscription is **deleted** and the reminder is not stuck.
2. Force a transient send error (mock) → bounded retries, then give up without crashing the
   tick.
3. Deny browser permission → no subscription, but `GET /api/v1/reminders` still lists due
   reminders (push is best-effort).

## Test & gate commands

```bash
just test         # backend pytest (coverage ≥85%, per-module ≥70%) + frontend vitest
just lint         # ruff + eslint + prettier --check
just typecheck    # mypy --strict + tsc --noEmit
cd backend && python -m alembic check        # drift-free
python scripts/generate_openapi_client.py && git diff --exit-code frontend/src/api/v1.d.ts
```

Backend-only domain focus (fast loop):

```bash
cd backend && python -m pytest tests/domain/test_reminders.py tests/domain/test_reminder_dispatch.py tests/domain/test_refill_supply.py -v
```

Security spot-checks (FR-002/017, SC-009): grep logs/responses for the VAPID private key and
subscription `auth`/`p256dh` — they must never appear; run the cross-user negative tests
(`test_reminders_api.py`, `test_push_api.py`).

E2E (skip-gated, like the other smokes): `E2E_RUN_REMINDERS=1` enables `e2e/reminders.spec.ts`.
