# ADR-0002 — In-process APScheduler over Celery + Redis for v1 reminders

## Status

**Accepted** (Phase 7 — Reminders + Snooze). Refined from the original
proposal: durable per-reminder state lives in the project's own `reminders`
table, not APScheduler's `SQLAlchemyJobStore` — see the Decision section.

## Context

MedMinder needs to deliver scheduled reminders (dose times, refill
warnings) via Web Push. The realistic options are:

- **In-process APScheduler**, co-located with the FastAPI app on the
  Koyeb backend instance.
- **Celery + Redis**, a separate broker and worker pool.

The deployment context shapes the trade-off:

- Free-tier Koyeb gives us one always-on Eco Micro instance. Adding
  Redis means another paid or near-free service to manage.
- Reminder volume in v1 is bounded by user count × daily dose count.
  At single-user-per-account scale, this fits comfortably in a single
  process.
- Mission scope is single-tenant in feel; we're not building for
  thousands of concurrent users.

## Decision

Run APScheduler **inside the FastAPI process** for v1. Use the
`AsyncIOScheduler` so it shares the event loop with the web app.

**Durable state lives in the project's own `reminders` table, not
APScheduler's `SQLAlchemyJobStore`** (refined at acceptance). The scheduler
runs a *single recurring "dispatch tick"* job (interval, re-registered at
every startup with a fixed id) using the **default in-memory job store**; the
tick scans the Alembic-managed `reminders` table for due rows, delivers them,
and marks them. A process restart therefore doesn't lose pending reminders —
they are rows in our table, which the next tick picks up.

Why not `SQLAlchemyJobStore` (the original proposal): production runs the app
under a **DML-only runtime DB role** (no DDL — see `docs/deployment.md`), and
the jobstore issues `CREATE TABLE` for its `apscheduler_jobs` table on start,
which that role cannot run; it would also fight the CI `alembic check` drift
gate (the table isn't in `Base.metadata`). The reminders-table-as-truth model
sidesteps both and is a cleaner fit, since reminders are created/cancelled by
many triggers (schedule edits, doses, snoozes, refills) that simply write rows.

The Koyeb Eco Micro instance is chosen specifically because it does
not sleep, which is a hard requirement for in-process scheduling to
work reliably (see `docs/deployment.md`). v1 runs a **single instance**;
two would each fire the tick and double-deliver (revisit this ADR before
scaling out).

## Consequences

### Positive
- **One process, one deploy.** No second service, no broker
  configuration, no inter-process serialization concerns.
- **Free-tier compatible.** Stays within the deployment budget
  documented in `docs/deployment.md`.
- **Restart-safe.** Pending reminders are rows in the Alembic-managed
  `reminders` table, so a restart can't lose them; the scheduler's single
  tick is re-registered on startup. No second store to keep in sync.

### Negative
- **No horizontal scaling.** Two app instances would each try to fire
  the same job. v1 explicitly runs a single instance; if we ever
  scale out, this ADR must be revisited.
- **Job execution shares the web event loop.** A long-running
  reminder dispatch could starve HTTP handlers. Mitigated by keeping
  push delivery non-blocking and bounded.
- **Failure mode is the whole app.** A bad scheduler bug could crash
  the web tier. Mitigated by isolating reminder logic and exhaustive
  unit tests.

### Neutral
- Migration to Celery + Redis is well-trodden if we outgrow this
  decision; the domain logic dispatching reminders should be written
  to be transport-agnostic (the scheduler calls a function; that
  function does not know whether it was invoked by APScheduler or
  Celery).
