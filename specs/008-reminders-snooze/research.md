# Phase 0 Research — Phase 7 (Reminders + Snooze)

Decisions that resolve the technical unknowns the spec deferred to `/speckit-plan`. Each is
**Decision / Rationale / Alternatives considered**. The user-facing forks were already settled
in `spec.md` Clarifications; this file covers the *engineering* choices.

---

## D1 — Scheduler architecture: reminders-table-as-truth + recurring tick (refines ADR-0002)

**Decision**: Run an in-process **`AsyncIOScheduler`** (APScheduler 3.x), started in the
FastAPI lifespan, with a **single recurring "dispatch tick"** job (interval
`reminder_tick_seconds`, default 30s) and the **default in-memory job store**. The durable
per-reminder state is the existing Alembic-managed **`reminders` table** — the tick scans it
for due rows, sends them, and marks them. We do **not** use APScheduler's `SQLAlchemyJobStore`.

**Rationale**:
- ADR-0002's real intent is *in-process scheduling, single instance, free-tier, survives
  restart* — not the specific persistence mechanism. Reminder rows in our own table satisfy
  "restart doesn't lose pending reminders" directly and are already Alembic-managed.
- **Hard blocker against `SQLAlchemyJobStore`**: the constitution + `docs/deployment.md`
  mandate a **DML-only runtime DB role** (no DDL). `SQLAlchemyJobStore` issues
  `CREATE TABLE` for its `apscheduler_jobs` table on start — which the runtime role cannot
  run — and that table would also fight `alembic check` drift detection (it isn't in
  `Base.metadata`). Avoiding the jobstore sidesteps both.
- The feature creates/cancels reminders from **many** triggers (schedule edits, doses,
  snoozes, refills). A table-as-truth model means those triggers just write rows and a single
  dispatcher sends them — far simpler than churning `add_job`/`remove_job` and keeping a
  second source of truth (apscheduler_jobs) in sync.
- A single recurring tick needs **no** persistence: it's re-registered at every startup with a
  fixed id (`replace_existing=True`), so the in-memory store is sufficient.
- 30s granularity meets SC-003 (snooze ±1 min) and HH:MM dose slots at single-tenant volume.

**This refines ADR-0002**, whose *Proposed* text named `SQLAlchemyJobStore`. The **Accepted**
ADR (this phase) documents the table-as-truth choice and the dual-role rationale. Per the
constitution, the divergence is reconciled in the same PR (the ADR edit).

**Alternatives considered**:
- *`SQLAlchemyJobStore`, one job per reminder fire* — rejected: DML-only-role DDL blocker,
  `alembic check` drift, dual source of truth, heavy job churn on every schedule/dose change.
- *`SQLAlchemyJobStore` for the single tick only* — rejected: still requires the jobstore
  table (same DDL/drift problems) for zero benefit over re-registering one in-memory job.
- *Celery + Redis* — rejected by ADR-0002 (extra service, off free-tier budget).
- *APScheduler 4.x (async-native job store)* — rejected: still alpha/beta; pin policy wants a
  stable upper-bounded release. Revisit if we ever outgrow single-instance.

---

## D2 — Single-instance guarantee & test/CI gating

**Decision**: The scheduler starts **once**, in the app lifespan, only when
`settings.reminders_enabled` is true. Tests, CI, and Alembic invocations run with
`reminders_enabled=False` (the dispatch/orchestration functions are tested directly, no
running scheduler). Production runs a **single uvicorn worker** (already the deployment
shape, ADR-0002).

**Rationale**: Two workers/instances would each fire the tick and double-deliver. A settings
flag keeps the test suite deterministic (no background loop racing the rollback fixture) and
lets the domain logic be unit-tested in isolation (Principle III). Documented in
`docs/deployment.md` and the Accepted ADR-0002.

**Alternatives**: a DB advisory lock so only one instance's tick is active — deferred to the
"if we scale out" revisit in ADR-0002; unnecessary at v1's single instance.

---

## D3 — Dose-reminder generation: idempotent rolling horizon

**Decision**: A `generate_due_dose_reminders(session, *, now, horizon)` routine (run by the
tick, default horizon 48h) ensures a **`pending` dose `reminders` row exists for each upcoming
(schedule, fire-instant)** within the horizon, for every non-deleted schedule that has ≥1
non-deleted attached medication. Generation is **idempotent**: it checks for an existing
non-`dismissed` reminder at `(schedule_id, scheduled_for)` before inserting. Fire instants are
computed in the **owning user's timezone** from `schedule.time_of_day` + `days_of_week` mask,
then converted to UTC (reusing the `domain/timezone.py` zone-resolution pattern; the pure math
lives in `domain/reminders.py`).

**Rationale**: Materialising dose reminders (rather than computing slots on the fly) is what
makes them listable (FR-008), snoozeable, dismissable, and markable `sent` with a lifecycle
(FR-006). A rolling 48h horizon keeps the table small and tolerates a day or two of downtime.
Idempotency makes generation safe to run every tick and after every schedule mutation.

**Alternatives**: pre-generate far ahead (rejected — table bloat, more to rewrite on schedule
edits); compute slots on the fly with no rows (rejected — can't model lifecycle/snooze/dismiss
or the overdue list).

---

## D4 — Dispatch, misfire grace, and coalescing

**Decision**: `dispatch_due_reminders(session, *, now, grace, send)` selects `pending`
reminders with `scheduled_for <= now`, ordered oldest-first, and for each:
- If `now - scheduled_for <= grace` (`reminder_grace_minutes`, default 15) → **deliver** (call
  `send` for each of the user's subscriptions) and mark `sent`.
- If older than `grace` → **do not push, do not mark sent**; the row stays `pending` (overdue)
  so it remains visible in-app until taken/dismissed (FR-006a).
**Coalescing** is structural: each (schedule, fire-instant) is a single row; marking it `sent`
once prevents a second push, and distinct days are distinct rows, so a recurring slot never
double-fires.

**Rationale**: Implements the clarified "bounded grace + coalesce" exactly, with the policy in
testable pure helpers (`is_within_grace`) and the I/O in the orchestrator. Best-effort,
non-blocking: a failed/slow `send` for one subscription never blocks the tick (D6).

**Alternatives**: APScheduler's built-in `misfire_grace_time`/`coalesce` (rejected — those
apply to APScheduler *jobs*, but our truth is the reminders table, not jobs).

---

## D5 — Quiet-hours deferral (midnight-wrap)

**Decision**: At dispatch, before sending, `defer_for_quiet_hours(fire_utc, tz, qh_start,
qh_end)` (pure, in `domain/reminders.py`) decides: if the reminder's local fire time is inside
`[qh_start, qh_end)` (handling the wrap case where `qh_start > qh_end`, e.g. 22:00→07:00, as
spanning midnight), return the **window-end instant** (today or tomorrow as appropriate, in
UTC); otherwise return `None`. When non-`None`, the dispatcher **updates the row's
`scheduled_for` to the deferred instant** and leaves it `pending` — a later tick at the window
end delivers it. Users with `quiet_hours_start`/`_end` NULL are never deferred. The boundary
is **exclusive at the end** (a reminder exactly at `qh_end` fires).

**Rationale**: Deferral-by-rescheduling keeps a single mechanism (the tick scans `pending`)
and is naturally idempotent. The wrap math is the one tricky bit, so it's pure and
exhaustively unit-tested (mirrors how `domain/timezone.py` isolates DST/midnight edges).
Applies to refill warnings too (a refill row generated during quiet hours is recorded
immediately, visible in-app, push deferred) — per the spec assumption.

**Alternatives**: compute the deferral at generation time (rejected — quiet hours can change,
and refill/snooze reminders are created ad hoc; deciding at dispatch is the single correct
point).

---

## D6 — Web Push delivery: pywebpush via a thread, with gone-subscription cleanup

**Decision**: `domain/push.py` wraps **`pywebpush`** (VAPID-signed). Because `pywebpush` is
synchronous, each send runs via **`asyncio.to_thread`** so it never blocks the event loop /
dispatch tick. The dispatcher sends to each of the user's subscriptions concurrently
(bounded), catching per-send exceptions so one failure can't abort the batch (FR-007). A
`WebPushException` whose response status is **404 or 410 (Gone)** marks the subscription for
**deletion** (FR-016); other (transient) errors are retried up to a configurable maximum
**`reminder_send_max_attempts` (default 3)** then given up. The single `# type: ignore[import-untyped]` for the un-stubbed
`pywebpush` is isolated here with a rationale comment (Principle II).

**Rationale**: `pywebpush` is the de-facto Python Web Push library and bundles `py-vapid`;
running it off-thread keeps the async app responsive. 404/410 is the standard "subscription
expired" signal, so cleanup prevents dead endpoints accumulating.

**Alternatives**: a pure-async push library (rejected — none mature/maintained enough to pin);
hand-rolling VAPID + `aiohttp` (rejected — re-implements `pywebpush` + `http-ece` crypto, more
security surface).

---

## D7 — VAPID keys: env-only secret + Python keygen script

**Decision**: Three new settings — `vapid_public_key`, `vapid_private_key` (**secret**),
`vapid_subject` (`mailto:` contact). The **public** key is served by
`GET /api/v1/push/vapid-public-key`; the **private** key is never sent, logged, or returned
(FR-002/SC-009). A new **`scripts/generate_vapid_keys.py`** (Python, cross-platform per
Principle V) prints a key pair for operators to paste into env/secret stores. In development,
empty keys are allowed: push sends are skipped (logged at debug) while reminders are still
recorded — so the loop is testable without configuring push.

**Rationale**: Matches the existing secret-handling pattern (`SESSION_SECRET` in
`settings.py`): env-only, dev fallback that degrades safely. A Python keygen script avoids a
`.sh`/`.ps1` pair.

**Alternatives**: generating keys at boot if unset (rejected — keys must be **stable** across
restarts or every client resubscribes; explicit operator-provided keys are correct). Requiring
keys even in dev (rejected — blocks local/test runs of the rest of the feature).

---

## D8 — Reminder index migration (no tables/columns)

**Decision**: One Alembic revision `0006_reminder_indexes.py` adds, declared on the `Reminder`
model so `alembic check` stays green:
- `ix_reminders_dispatch` — partial index on `scheduled_for` `WHERE status = 'pending'` (the
  hot dispatch scan).
- `ix_reminders_user_status` — `(user_id, status)` (the in-app list).
- `uq_reminders_open_refill` — **partial UNIQUE** on `medication_id`
  `WHERE type = 'refill' AND status <> 'dismissed'` (DB-enforces "at most one open refill
  warning per medication", FR-014).
No new tables or columns: the Phase 1 `reminders`/`push_subscriptions` schema and the
`medications.refill_count`/`refill_threshold` columns already exist.

**Rationale**: The partial-unique index turns the refill-dedup invariant into a DB guarantee
(belt-and-suspenders with the app-level check), and the two read indexes keep the scan/list
fast. Declaring them on the model is required for drift-free `alembic check`.

**Alternatives**: app-level dedup only (rejected — a race could double-insert; the DB
constraint is cheap insurance); a `warned_at` column on medications (rejected — the spec chose
"no new column"; an open refill reminder *is* the signal).

---

## D9 — Reschedule on schedule mutation & refill re-arm hooks

**Decision**:
- **Schedule mutations** (`api/schedules_crud.py` create/update/delete) and **med
  attach/detach** (`api/medications.py` save) call
  `regenerate_schedule_reminders(session, schedule_id)`: delete the schedule's **future
  `pending`** dose reminders and re-generate them from current state (a no-op delete on
  create; a full cancel on delete/detach). `sent`/`dismissed`/past rows are untouched (history
  preserved). (FR-012)
- **Refill re-arm**: `domain/medications.py` update compares old/new `refill_count`; if it
  rises **above** `refill_threshold`, it resolves (`dismissed`) any open refill reminder for
  the med, re-arming a future warning (FR-014a).
- **Resolve-on-take**: `create_dose` marks today's `pending`/`snoozed` dose reminder(s) for
  the taken (schedule slot) as `dismissed` (FR-021).

**Rationale**: Keeping (re)generation in the routers that own the mutating writes (within the
same transaction) guarantees reminders always match current state with no stale/missing rows
(SC-005). Operating only on **future `pending`** rows preserves the audit trail of what was
already sent.

**Alternatives**: a periodic reconciliation sweep instead of synchronous regeneration
(rejected — a lag window would leave stale reminders; the synchronous hook is exact and the
rolling generation tick is a safety net, not the primary path).

---

## Resolved unknowns checklist

| Spec-deferred item | Resolved by |
|---|---|
| Reminder generation strategy | D3 (idempotent rolling 48h horizon, materialised rows) |
| Scheduler/job persistence | D1 (reminders-table-as-truth; in-memory job store; refines ADR-0002) |
| Misfire grace duration / coalesce | D4 (`reminder_grace_minutes` default 15; structural coalesce) |
| Quiet-hours wrap & deferral point | D5 (pure wrap math; defer-by-reschedule at dispatch) |
| Web Push transport library | D6 (`pywebpush` via `asyncio.to_thread`; 404/410 cleanup) |
| VAPID key handling | D7 (env-only secret; Python keygen; dev-skip) |
| Endpoint/migration shapes | D8 (indexes only, no tables/columns) + contracts/reminders.openapi.yaml |
| Retry/backoff specifics | D6 (`reminder_send_max_attempts` default 3; gone → delete) |
| Reschedule + re-arm wiring | D9 (router hooks within the mutating transaction) |
| Quiet-hours configuration path | D10 (admin CLI + `update_user`, like `timezone`) |
| Void over-restore edge | D10 (restore only when `refill_count` is set) |

---

## D10 — Quiet-hours configuration & void over-restore guard (analysis follow-ups)

**Decision (quiet-hours config, U2)**: Quiet hours are **admin-managed like `timezone`**.
Extend `domain/users.update_user` with `new_quiet_hours_start`/`new_quiet_hours_end` (set or
clear, validated `HH:MM`) and add `--quiet-hours-start`/`--quiet-hours-end` to the
`medminder-admin user update` CLI. No in-app editor in Phase 7 (consistent with the minimal
scope); tests may also set the columns via a fixture.

**Rationale**: FR-011 only *enforces* quiet hours, but the columns had **no setter** anywhere
(the CLI `user update` exposed only email/name/role/password) — so US3 was untestable and the
feature unusable in production. `timezone` is already a CLI-set user preference; quiet hours
follow the same admin-managed pattern with a minimal, consistent surface.

**Decision (void over-restore, U3)**: `void_dose` restores `refill_count` by one **only when
it is set** (NULL → no-op). The listed edge case "voiding a dose that did not decrement (med
had no count)" is thereby satisfied. Because individual doses carry no per-dose supply ledger,
the residual case (med untracked at take, given a count later, then voided) may over-count by
one — an **accepted, user-correctable** limitation (edit the med), documented in FR-013, not a
guard failure. A per-dose supply ledger is out of scope for v1.

**Alternatives considered**: an in-app quiet-hours editor (deferred to Phase 8 with the rest of
the notification UX); a per-dose supply ledger to make void exact (rejected — disproportionate
for a single-tenant counter; revisit only if supply accuracy becomes a real complaint).
