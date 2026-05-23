# MedMinder — Glossary

Terms used across the constitution (`specs/`), user stories
(`docs/user_stories.md`), and design notes (`docs/design/`).

| Term | Definition |
|------|------------|
| **Adherence** | Whether a user actually takes their medication as scheduled, measured over time. The calendar and stacked-bar views in UC-6 visualize adherence. |
| **Admin** | A user with `role = 'admin'`, created via the `medminder-admin` CLI. Admins can manage other users via the same CLI; there is no admin web UI in v1. |
| **Append-only** | Describes the `doses` table: rows are inserted but never updated or deleted. Corrections are made by inserting a compensating row, preserving history. |
| **Argon2id** | Password-hashing algorithm used for `users.password_hash`. Slow by design to resist offline cracking. |
| **Bootstrap admin** | The first admin user, created on a Koyeb one-shot job after the initial deploy via `medminder-admin user add`. See `docs/deployment.md` §2.3. |
| **Cooldown** | The minimum time that must elapse before a dose is permitted, either because of a `count_down` timer's `min_interval_minutes` or because of a `medication_interactions` rule. |
| **Course size** | `medications.total_doses` — the total doses in a fixed-duration prescription (e.g., a 14-pill antibiotic course). Distinct from refill inventory. |
| **Daily cap** | `medications.max_doses_per_day` — for a `multi_sub_dose` med, the maximum non-voided doses allowed across the whole day, enforced alongside the max-at-a-time cap. Exceeding it raises a `daily_cap_reached` 409 (a non-overridable overdose guard). |
| **Max at a time** | For a `multi_sub_dose` med, `medications.times_per_day` reinterpreted as the maximum number of doses whose rolling windows may overlap at once (the per-dose concurrency cap). Exceeding it raises a `window_full` 409. See [[Rolling window]] and ADR-0010. |
| **Drug interaction** | A rule in `medication_interactions` saying "don't take medication A within N minutes of medication B." Symmetric in semantics; stored as a single asymmetric row (D5 in the Phase 1 spec). |
| **Interaction window** | The period after taking medication A during which medication B cannot be taken (Migraine Molly's case). |
| **Min-interval** | `medications.min_interval_minutes` — the cooldown between consecutive doses of a single PRN medication (Headache Harry's case). |
| **Out-of-schedule dose** | A take on `/today` that is off the schedule's day-of-week today, or more than ±2h from the slot's time. It is allowed but gated by a confirm modal (per-row, and once-per-group for "Take all"). PRN rows are never out-of-schedule. |
| **PHI** | Protected Health Information. Medication records and password hashes are treated as PHI for handling purposes (backups, logs) even though MedMinder is not formally a HIPAA-covered system. |
| **Pill-based dosage** | A med with `pill_strength` + `pills_per_dose` both set; `quantity_per_dose` is then derived server-side (`pill_strength * pills_per_dose`) rather than entered directly. Both columns are NULL for quantity-based meds (paired by CHECK). |
| **PRN** | Latin *pro re nata*, "as needed." A medication taken when symptoms occur rather than on a fixed schedule. Modeled with `timer_preference = count_down` and a `min_interval_minutes`. Unscheduled timer meds surface on `/today` (under "As needed") while their timer is running. |
| **Profile editor** | The in-app modal (opened by clicking your name in the nav bar) where a signed-in user changes their own **display name** (`PATCH /me`) and **password** (`POST /me/password`) — so the admin never knows the user's password. The login email stays admin-managed (CLI). A password change re-authenticates with the current password and signs the user out of their other devices. See ADR-0011. |
| **Push subscription** | A Web Push API endpoint registered for a user's device. Stored in `push_subscriptions`. One row per (user, device) pair. |
| **Quiet hours** | A per-user window (`users.quiet_hours_start` / `_end`) during which reminders are deferred. Wraps midnight correctly (UC-5.3). |
| **Refill warning** | A `reminders` row of `type = 'refill'`, scheduled when `medications.doses_remaining` falls below a threshold. |
| **Schedule** | A `schedules` row defining a time-of-day and a day-of-week bitmask. Schedules are **shared user-level resources** managed via `GET/POST/DELETE /api/v1/schedules`; medications attach to them by id via `schedule_medications` (one schedule can serve many meds). |
| **Snooze** | Re-scheduling a triggered reminder for one hour later (UC-5.2). The original reminder transitions to `status = 'snoozed'` and a new reminder is created. |
| **Soft delete** | Marking a row with `deleted_at TIMESTAMPTZ` instead of removing it. Applies to `users`, `medications`, and `schedules` per Phase 1 D6. |
| **Rolling window** | For a `multi_sub_dose` med, each dose is "active" for `window_duration_minutes` after it is taken. A new dose is blocked while the max-at-a-time cap (`times_per_day`) of rolling windows already overlaps; the oldest active dose frees a slot when its window expires (`taken_at + window`). Replaced the original tiled single-window model — see ADR-0010. |
| **Sub-dose** | One of the small, staggered doses of a `multi_sub_dose` med (Billy Bat's T3 split), each opening its own [[Rolling window]]. |
| **Timer mode** | One of `none`, `count_up`, `count_down`, `multi_sub_dose`. Stored in `medications.timer_preference`. See `docs/design/timer-modes.md`. |
| **Voiding** | Insertion of a compensating dose row that cancels a previous "taken" entry. Used by UC-4.2 (un-take). The original row is never deleted. |
