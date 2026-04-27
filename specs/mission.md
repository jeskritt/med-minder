# MedMinder — Mission

## Vision

MedMinder is a personal medication tracker that helps individuals take the right medication at the right time, confirm what they have already taken, and produce an honest record of adherence over time. It is delivered as a mobile-first Progressive Web App so it travels with users on the device they always have on them.

The product is single-tenant in feel: there is no public sign-up. Accounts are provisioned by an administrator via a CLI tool. This keeps the surface area small, removes a class of abuse vectors, and lets us focus the product on the daily medication-taking experience instead of growth machinery.

## Target users

The personas below are drawn from `docs/user_stories.md` and define the v1 product surface.

- **Granny Smith** — fixed-schedule daily medications (morning / afternoon / evening). Needs an unmistakable "taken / not taken" indicator with a timestamp, and a printable medication list for paperwork.
- **Billy Bat** — short-term acute pain meds with multiple sub-doses inside a single dosing window. Needs reminders that can be snoozed mid-task.
- **Migraine Molly** — drug-interaction-aware scheduling. Some medications cannot be combined, and others have mandatory cool-down periods between them.
- **Headache Harry** — PRN ("as needed") medication with a minimum interval between doses. Forgetful; needs to look at the app and instantly know whether he has already dosed and when.
- **Diabetic Dan** — recurring medications at flexible times of day, with snoozeable reminders.

## Core capabilities (v1 scope)

- Admin-managed users via CLI; no self-registration.
- Email + password login with server-side sessions.
- Add, edit, and delete medications with name, dosage, frequency, start date, and end date.
- Mark a dose as taken; persist a timestamp; allow correcting a mistaken "taken" via confirmation modal.
- Per-medication timer modes:
  - **None** — simple boolean "taken today" flag (Granny).
  - **Count-up** — time since last dose (Molly's interaction window).
  - **Count-down** — time until the next dose is permitted (Harry).
  - **Multi-sub-dose** — split timer bar for staggered sub-doses inside a dosing window (Billy).
- Local + Web Push reminders, with one-hour snooze and quiet hours.
- Long-term adherence view (calendar and/or stacked bar, color-coded) for retrospective questions like "did I take my BP medication yesterday?".
- Printable medication summary suitable for medical paperwork.

## Non-goals (v1)

These are explicitly out of scope to keep the product honest about YAGNI.

- No self-registration, password reset by email, or social login.
- No multi-tenant or organization features; no sharing between users.
- No pharmacy, e-prescribing, or insurance integrations.
- No clinician-facing views, caregiver portals, or third-party sharing.
- No AI features.
- No native mobile builds — PWA only.

## Success criteria

- Every persona in `docs/user_stories.md` can complete their primary flow end-to-end against a deployed build.
- Full automated test suite (unit, integration, E2E) is green in CI.
- Accessibility baseline: keyboard-only and screen-reader navigation works for login, medication list, mark-as-taken, and reminder snooze.
- Installable as a PWA on iOS and Android, with working push notifications.

## Engineering principles

These are binding rules, not aspirations. They come directly from the Developer Story in `docs/user_stories.md`.

- **SOLID, KISS, DRY, YAGNI** — applied at function, module, and service boundaries.
- **Fully typed** — Python with `mypy --strict`; TypeScript with `strict: true`.
- **Small units** — reasonably sized functions and files; no deeply nested code or conditional logic; no deeply nested data models.
- **Loose coupling** — clear seams between domain logic, persistence, transport, and UI. Domain logic must be testable without a database or HTTP server.
- **Minimal duplication** — one source of truth for each concept; in particular, no parallel hand-maintained code/data models on the frontend and backend.
- **No dead code** — unused code is deleted, not commented out.
- **Easily testable** — pure functions where possible; dependency-injected I/O.
- **Documented** — `docs/` carries ADRs for non-obvious decisions, ER diagrams for the data model, state diagrams for timer/reminder logic, sequence diagrams for key user flows, and the user stories themselves.
