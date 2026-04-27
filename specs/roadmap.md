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

## Phase 1 — Data model & migrations

- Tables: `users`, `medications`, `schedules`, `doses` (taken events), `reminders`.
- Alembic baseline migration.
- ER diagram committed to `docs/diagrams/er.md`.

## Phase 2 — Admin CLI for user management

Implements the "Registering for an account" use cases from `docs/user_stories.md`.

- Typer app with `user add | delete | update | list`.
- Argon2id password hashing.
- Role field (`admin` | `user`).
- Tests against a real Postgres in CI.

## Phase 3 — Auth (login / logout)

- Session cookie auth (signed, HTTP-only, SameSite=Lax).
- Login page; logout endpoint and button.
- Auth-required route guards on both backend and frontend.
- Sequence diagram for the login flow in `docs/diagrams/`.

## Phase 4 — Medications CRUD (Granny baseline)

- List, add, edit, delete medications.
- Fields: name, dosage, frequency, start date, end date.
- Printable medication list view (clean print stylesheet).

## Phase 5 — Mark-as-taken + timestamped history

Covers Granny's and Harry's primary need: "did I take it, and when?"

- "Taken" toggle with persisted timestamp.
- Confirmation modal when un-taking ("This med has already been taken. Remove the 'taken' status?").
- Per-medication "today" view.

## Phase 6 — Timer modes

State machine per timer mode; state diagram per mode in `docs/diagrams/`.

- **6a** — Count-up since last dose (Molly's interaction window).
- **6b** — Count-down with min-interval guard (Harry's PRN cooldown).
- **6c** — Multi-sub-dose timer bar (Billy's staggered dosing inside a window).

## Phase 7 — Drug-interaction cooldowns

For Molly: "cannot take X within N hours of Y" rules with clear UI warnings before the user can mark the conflicting med as taken.

## Phase 8 — Reminders + snooze

- Scheduled reminders via APScheduler.
- Web Push delivery with VAPID keys.
- One-hour snooze action.
- Quiet hours per user.

## Phase 9 — PWA polish

- `vite-plugin-pwa` configured; manifest, icons, theme color.
- Offline app shell.
- Push permission UX flow.
- Verified installable on iOS Safari and Android Chrome.

## Phase 10 — Long-term adherence views

- Calendar and/or stacked-bar view of adherence per medication.
- Color coding for taken / missed / skipped.
- CSV export.

## Phase 11 — Hardening

- Accessibility pass (keyboard, screen reader, contrast) on primary flows.
- Performance budgets enforced in CI (Lighthouse PWA score, bundle size).
- Final, comprehensive security review covering session handling, CSRF, push key handling, input validation, dependency audit, and a sweep of audit logging — building on the per-phase reviews already required by the exit criteria.
- End-to-end Playwright suite covering each persona's primary flow from `docs/user_stories.md`.
