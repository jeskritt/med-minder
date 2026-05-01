# ADR-0002 — In-process APScheduler over Celery + Redis for v1 reminders

## Status

Proposed — moves to **Accepted** with the Phase 7 (Reminders) PR.

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
`AsyncIOScheduler` so it shares the event loop with the web app. Job
state is persisted to the project Postgres via APScheduler's
`SQLAlchemyJobStore`, so a process restart doesn't lose pending
reminders.

The Koyeb Eco Micro instance is chosen specifically because it does
not sleep, which is a hard requirement for in-process scheduling to
work reliably (see `docs/deployment.md`).

## Consequences

### Positive
- **One process, one deploy.** No second service, no broker
  configuration, no inter-process serialization concerns.
- **Free-tier compatible.** Stays within the deployment budget
  documented in `docs/deployment.md`.
- **Persistent jobs.** `SQLAlchemyJobStore` means restarts don't lose
  pending reminders.

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
