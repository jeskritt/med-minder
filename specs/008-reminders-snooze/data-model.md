# Phase 1 Data Model — Phase 7 (Reminders + Snooze)

Phase 7 adds **no new tables or columns**. It activates the dormant Phase 1 tables
(`reminders`, `push_subscriptions`) and the dormant `medications` supply columns, and adds
**indexes + one partial-unique constraint** (see `0006_reminder_indexes.py`). This document
records the entities as used by this feature, the reminder **lifecycle state machine**, and
the new indexes.

## Entities used

### `reminders` *(existing — given behavior by this phase)*

| Column | Type | Notes (Phase 7 usage) |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid FK→users, CASCADE, indexed | Owner; every query is scoped to it. |
| `type` | enum `dose` \| `refill` | Dose → tied to a schedule; refill → tied to a medication. |
| `medication_id` | uuid FK→medications, CASCADE, nullable | Set iff `type='refill'` (existing CHECK). |
| `schedule_id` | uuid FK→schedules, CASCADE, nullable | Set iff `type='dose'` (existing CHECK). |
| `status` | enum `pending`\|`sent`\|`snoozed`\|`dismissed` | Lifecycle below. `server_default 'pending'`. |
| `scheduled_for` | timestamptz | The UTC fire instant. Mutated when a quiet-hours deferral reschedules it (D5). |
| `created_at` / `updated_at` | timestamptz | |

**Existing CHECK `ck_reminders_type_refs`** (unchanged, relied upon):
`(type='dose' AND schedule_id IS NOT NULL AND medication_id IS NULL) OR
(type='refill' AND medication_id IS NOT NULL AND schedule_id IS NULL)`.
→ confirms the clarified decision that **dose reminders are per-schedule** (one row per
schedule slot; the notification names the medication(s) attached to that schedule), and
**refill reminders are per-medication**.

### `push_subscriptions` *(existing — given behavior by this phase)*

`endpoint` (Text), `p256dh` (Text), `auth` (Text), unique per `(user_id, endpoint)`. Created
on enable (idempotent upsert), deleted on disable or when a send reports the endpoint **gone**
(404/410, D6). No new PII — these are the W3C Push Subscription fields, minimised (FR-002/017).

### `users` *(existing — read only)*

`timezone` (IANA) drives local fire-time computation; `quiet_hours_start` / `quiet_hours_end`
(nullable `time`) drive deferral (D5). Phase 7 adds a quiet-hours **setter** to the admin CLI /
`update_user` (D10) — admin-managed like `timezone` — and enforces the columns at dispatch;
there is no in-app quiet-hours editor.

### `medications` *(existing — `refill_count` becomes live)*

`refill_count` (nullable int, ≥0) is the **authoritative live on-hand count**, mutated by
take/void (D9). `refill_threshold` (nullable int, ≥0) is the warn-at level. The legacy
`doses_remaining` / `total_doses_filled` columns are **not used** by this feature (the
glossary/UC-5.4 drift is corrected in the doc sweep). Existing CHECKs
(`refill_count >= 0`, `refill_threshold >= 0`) already floor the count at zero (FR-013).

## Reminder lifecycle (state machine)

```text
            generate (dose)                    take crosses threshold (refill)
                  │                                          │
                  ▼                                          ▼
              ┌─────────┐   dispatch within grace      ┌──────────┐
              │ pending │ ───────────────────────────▶ │   sent   │
              └─────────┘                              └──────────┘
                 │  │  ▲                                    │  │
   snooze (in-app)│  │  │ (overdue: older than grace —      │  │ snooze (in-app): mark
   mark snoozed + │  │  │  stays pending, never pushed,     │  │ snoozed + new pending +1h
   new pending+1h │  │  │  visible in-app)                  │  │
                  ▼  │  └───────────────────────────────────┘  │
              ┌──────────┐                                      │
              │ snoozed  │ (terminal for the original)          │
              └──────────┘                                      │
                  │ take / manual-dismiss / refill re-arm       │
                  ▼                                             ▼
              ┌───────────┐ ◀──────────────────────────────────┘
              │ dismissed │  (terminal: resolved by take, manual dismiss,
              └───────────┘   or refill_count raised back above threshold)
```

- **pending → sent**: dispatch tick delivers within the grace window (D4).
- **pending (overdue)**: due but older than grace → not pushed, stays `pending`, shown
  in-app as overdue until taken/dismissed (FR-006a).
- **pending/sent → snoozed**: user snoozes in-app → original becomes `snoozed` (terminal) and
  a **new `pending`** reminder is created at `now + 1h` (FR-009); re-snooze allowed (FR-010).
- **→ dismissed** (resolution, FR-021/022/014a): recording a dose resolves today's
  pending/snoozed dose reminder(s) for the slot; the user can manually dismiss any reminder;
  raising `refill_count` above `refill_threshold` resolves the open refill reminder.
- **Quiet-hours deferral** is not a status change — it updates `scheduled_for` and the row
  stays `pending` (D5).

## Supply transitions (`medications.refill_count`)

| Trigger | Effect | Reminder side effect |
|---|---|---|
| `create_dose` (refill_count set) | `refill_count = max(0, refill_count - 1)` | If new value ≤ `refill_threshold` **and** no open refill reminder exists → create one `pending` refill reminder (FR-014). |
| `void_dose` (refill_count set) | `refill_count = refill_count + 1` (NULL → no-op, never restores into an untracked med) | (No automatic warning clear; re-arm is tied to crossing the threshold upward via edit.) Residual over-count for the untracked-at-take → set-later edge is accepted/user-correctable (FR-013). |
| `update` med raising `refill_count` above `refill_threshold` | persisted | Resolve (`dismissed`) any open refill reminder for the med → re-arm (FR-014a). |
| `refill_count` NULL | no supply tracking | Never warns (opt-in, FR-014). |

"Open refill reminder" = a `reminders` row with `type='refill'`, `medication_id = med.id`,
`status <> 'dismissed'` — enforced unique by `uq_reminders_open_refill` (D8).

## New indexes (migration `0006_reminder_indexes.py`)

Declared on the `Reminder` model (drift-free `alembic check`):

| Name | Definition | Purpose |
|---|---|---|
| `ix_reminders_dispatch` | partial index on `(scheduled_for)` `WHERE status='pending'` | Hot dispatch scan: due pending rows. |
| `ix_reminders_user_status` | `(user_id, status)` | In-app reminder list (FR-008). |
| `uq_reminders_open_refill` | partial UNIQUE on `(medication_id)` `WHERE type='refill' AND status <> 'dismissed'` | One open refill warning per med (FR-014). |

No change to `docs/diagrams/er.md` table shapes (indexes only); the ER doc's existing
`reminders` / `push_subscriptions` rows remain accurate.

## Cross-cutting invariants

- **Ownership**: every reminder/subscription read or write filters on `user_id = current
  user` (FR-017, SC-008). Snooze/dismiss load-by-id then assert ownership (404 otherwise).
- **Append-vs-mutate**: dose history (`doses`) stays append-only; reminders are mutable status
  rows (not audit). Schedule regeneration only deletes **future `pending`** dose reminders,
  never `sent`/`dismissed`/past rows (D9).
- **No secrets persisted in plaintext logs**: subscription `auth`/`p256dh` and the VAPID
  private key never appear in logs or responses (FR-002/017, SC-009).
