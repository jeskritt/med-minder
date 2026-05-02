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
| **Drug interaction** | A rule in `medication_interactions` saying "don't take medication A within N minutes of medication B." Symmetric in semantics; stored as a single asymmetric row (D5 in the Phase 1 spec). |
| **Interaction window** | The period after taking medication A during which medication B cannot be taken (Migraine Molly's case). |
| **Min-interval** | `medications.min_interval_minutes` — the cooldown between consecutive doses of a single PRN medication (Headache Harry's case). |
| **PHI** | Protected Health Information. Medication records and password hashes are treated as PHI for handling purposes (backups, logs) even though MedMinder is not formally a HIPAA-covered system. |
| **PRN** | Latin *pro re nata*, "as needed." A medication taken when symptoms occur rather than on a fixed schedule. Modeled with `timer_preference = count_down` and a `min_interval_minutes`. |
| **Push subscription** | A Web Push API endpoint registered for a user's device. Stored in `push_subscriptions`. One row per (user, device) pair. |
| **Quiet hours** | A per-user window (`users.quiet_hours_start` / `_end`) during which reminders are deferred. Wraps midnight correctly (UC-5.3). |
| **Refill warning** | A `reminders` row of `type = 'refill'`, scheduled when `medications.doses_remaining` falls below a threshold. |
| **Schedule** | A `schedules` row defining a time-of-day and a day-of-week bitmask. Medications attach to schedules via `schedule_medications`. |
| **Snooze** | Re-scheduling a triggered reminder for one hour later (UC-5.2). The original reminder transitions to `status = 'snoozed'` and a new reminder is created. |
| **Soft delete** | Marking a row with `deleted_at TIMESTAMPTZ` instead of removing it. Applies to `users`, `medications`, and `schedules` per Phase 1 D6. |
| **Sub-dose** | One of N partial doses inside a `multi_sub_dose` window (Billy Bat's T3 split). |
| **Timer mode** | One of `none`, `count_up`, `count_down`, `multi_sub_dose`. Stored in `medications.timer_preference`. See `docs/design/timer-modes.md`. |
| **Voiding** | Insertion of a compensating dose row that cancels a previous "taken" entry. Used by UC-4.2 (un-take). The original row is never deleted. |
