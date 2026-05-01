# MedMinder — Roadmap

Phases are intentionally small. Each phase ends with something runnable, typed, tested, and documented. A phase is not "done" until its **exit criteria** are met.

## Phase exit criteria (apply to every phase)

- All new code is fully typed (`mypy --strict`, `tsc --noEmit` clean).
- Unit and integration tests cover new behavior; CI is green.
- A relevant diagram in `docs/` is added or updated (ER, state, sequence).
- A new ADR is written for any non-obvious decision.
- No dead code, no commented-out code, no TODOs left without an issue.
- Security review of any new surface area is included in the PR: authn/authz checks on new endpoints, input validation at boundaries, secrets are env-only, dependencies added are pinned and reviewed, and any new data field is justified against data minimization.

---

## Phase 0 — Foundations

Stand up the skeleton so every later phase has somewhere to land.

- Repo layout per `specs/tech-stack.md`.
- `docker-compose.yml` for Postgres + backend + frontend.
- `justfile` (or `Makefile`) with `dev`, `test`, `lint`, `typecheck`, `migrate`.
- Pre-commit hooks and GitHub Actions CI skeleton.
- Backend: `/healthz` endpoint, app factory, settings via Pydantic.
- Frontend: "Hello MedMinder" page wired to `/healthz`.
- OpenAPI → TypeScript client generation pipeline.
- `docs/adr/0000-template.md`, empty `docs/diagrams/` with stubs.

## Phase 1 — Data model & admin CLI

Ship the v1 schema and the production-supported user-management path
together. The CLI shares the data layer it operates on, so bundling
1a + 1b exercises the schema through real CRUD before any HTTP code
exists.

### Phase 1a — Data model & migrations
- Tables: `users`, `sessions`, `medications`, `medication_interactions`,
  `schedules`, `schedule_medications` (M:M), `doses`,
  `reminders` (dose & refill types), `push_subscriptions`.
- User preferences on `users`: `timezone` (IANA), `quiet_hours_start`,
  `quiet_hours_end`.
- Soft delete on `users`, `medications`, `schedules`. `doses` are
  append-only.
- Alembic baseline migration.
- Postgres service container added to GitHub Actions CI; coverage gate
  (`pytest-cov`) enforced.
- ER diagram committed to `docs/diagrams/er.md`.

### Phase 1b — Admin CLI
Implements the "Registering for an account" use cases from `docs/user_stories.md`.

- Typer app `medminder-admin` with `user add | delete | update | list`.
- `db backup | restore` subcommands (wrappers around `pg_dump`/`pg_restore`).
- Argon2id password hashing in a shared domain module reused by Phase 2 auth.
- Soft-delete semantics for `user delete` (sets `deleted_at`, preserves history).
- Tests against the real Postgres service container from 1a.

## Phase 2 — Auth (login / logout)

- Session cookie auth (signed, HTTP-only, SameSite=Lax).
- Session token hashing via SHA-256 (random tokens, no KDF).
- Login page; logout endpoint and button.
- Auth-required route guards on both backend and frontend.
- Sequence diagram for the login flow in `docs/diagrams/`.
- ADR-0001 (sessions over JWTs) moves from `Proposed` to `Accepted`.

## Phase 3 — Medications CRUD (Granny baseline)

- List, add, edit, delete medications.
- Fields: name, dosage, unit, `times_per_day`, start date, end date,
  `total_doses` (course size), refill inventory fields.
- Mismatch warning when the count of attached schedules differs from
  `times_per_day`.
- Printable medication list view (clean print stylesheet).

## Phase 4 — Mark-as-taken + timestamped history

Covers Granny's and Harry's primary need: "did I take it, and when?"

- "Taken" toggle that writes a `doses` row with timestamp.
- Confirmation modal when un-taking ("This med has already been taken. Remove the 'taken' status?").
- Per-medication "today" view.
- **Smoke E2E** — the first Playwright test lands here, covering the
  Granny flow: log in, add a medication, mark a dose as taken, see it
  in today's list. Earlier than Phase 10 because mark-as-taken is the
  smallest end-to-end loop that proves the whole stack.

## Phase 5 — Timer modes

State machine per timer mode; state diagram per mode in `docs/diagrams/`.

- **5a** — Count-up since last dose (Molly's interaction window).
- **5b** — Count-down with min-interval guard (Harry's PRN cooldown).
- **5c** — Multi-sub-dose timer bar (Billy's staggered dosing inside a window).

ADR-0004 (timer state machines — modeled where, evaluated client-side
vs server-side) authored alongside 5a.

## Phase 6 — Drug-interaction cooldowns

For Molly: "cannot take X within N hours of Y" rules with clear UI
warnings before the user can mark the conflicting med as taken.
Symmetric enforcement: a single `medication_interactions` row guards
both directions.

## Phase 7 — Reminders + snooze

- Scheduled reminders via APScheduler.
- Web Push delivery with VAPID keys.
- Refill reminders when medication supply is running low.
- One-hour snooze action.
- Quiet hours per user.
- ADR-0002 (in-process APScheduler vs Celery) moves from `Proposed`
  to `Accepted` with the chosen approach documented.

## Phase 8 — PWA polish

- `vite-plugin-pwa` configured; manifest, icons, theme color.
- Offline app shell.
- Push permission UX flow.
- Verified installable on iOS Safari and Android Chrome.

## Phase 9 — Long-term adherence views

- Calendar and/or stacked-bar view of adherence per medication.
- Color coding for taken / missed / skipped.
- CSV export.

## Phase 10 — Hardening

- Accessibility pass (keyboard, screen reader, contrast) on primary flows.
- Performance budgets enforced in CI (Lighthouse PWA score, bundle size).
- Final, comprehensive security review covering session handling, CSRF, push key handling, input validation, dependency audit, and a sweep of audit logging — building on the per-phase reviews already required by the exit criteria.
- Full Playwright suite covering every persona's primary flow from `docs/user_stories.md` (extends the Phase 4 smoke test).
