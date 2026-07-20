# ADR-0021 — Client-side push subscription re-sync

## Status

**Accepted** (post-Phase 10 fix). Amends [ADR-0020](0020-encrypt-push-keys-at-rest.md).

## Context

ADR-0020 introduced Fernet encryption of `p256dh`/`auth` with **no migration and
no backfill**, on the stated basis that legacy plaintext rows would fail to
decrypt, be deleted as `gone`, and "the browser re-subscribes with fresh
encrypted keys".

**That self-healing did not exist.** Nothing in the frontend re-subscribed:
`enablePushNotifications` only ever ran from a user click on the Enable button.
The actual behaviour in production was:

1. The dispatch tick failed to decrypt a legacy row → `InvalidToken` → `gone=True`.
2. `dispatch_due_reminders` deleted the subscription row.
3. It then marked the reminder `sent` regardless — delivery was never checked.
4. The **browser's** `PushSubscription` was untouched, so `getPushStatus()` still
   returned `"subscribed"` and the UI kept reporting "Notifications are on for
   this device."
5. No code path ever re-registered it.

Every device that had subscribed before the Phase 10 deploy was silently and
permanently unsubscribed server-side, while the UI claimed everything was fine.
Because the entire reminder/push pipeline logged nothing, there was no signal
anywhere — the only observable symptom was that notifications stopped arriving.

## Decision

Three changes, one per failure in the chain above.

### 1. The client re-syncs its subscription on every app load

`syncPushSubscription()` (`frontend/src/lib/push.ts`) reads the subscription the
browser already holds and re-POSTs it to `/api/v1/push/subscriptions`. That
endpoint was already idempotent — existing `(user, endpoint)` refreshes the key
material, missing inserts — so no backend change was needed to make repair work.

It **never calls `subscribe()` and never prompts for permission**: it only
mirrors existing browser state, so a user who has not opted in is unaffected.
Mounted via `useSyncPushSubscription(Boolean(user))` in `NavBar`, which renders
on every authenticated route. Fire-and-forget — a failure is swallowed rather
than surfaced, since this is a repair the user never asked for.

This makes the ADR-0020 claim true after the fact, and generalises: it repairs
*any* server-side subscription loss (key rotation, manual deletion, restore from
an older backup), not just the encryption migration.

### 2. A reminder is only marked `sent` when something was actually delivered

`dispatch_due_reminders` now resolves a reminder when at least one send returned
`delivered=True`, **or** when the user has no subscriptions at all (in-app-only
by design — retrying forever would be wrong). A reminder with subscriptions but
no successful send stays `pending` so a later tick retries it within the grace
window.

### 3. The pipeline logs

`domain/push.py`, `domain/reminder_dispatch.py`, and `scheduler.py` now use
module loggers: scheduler start (with tick interval and whether VAPID is
configured), a one-line per-tick summary (`due/dispatched/failed/subs_dropped`),
a warning when VAPID is unconfigured, and a warning naming any subscription
dropped for failed decryption.

Logs carry the **endpoint hostname only** (`_host()` in `domain/push.py`), never
key material, tokens, or the endpoint path — the path contains a per-device
secret.

## Consequences

- **Positive**: subscription loss self-heals within one app open, on any cause.
  Reminders are no longer burned by a failed send. A recurrence is visible in the
  Render logs rather than silent.
- **Negative / accepted**: one extra POST per session per device — negligible at
  this scale. A permanently failing endpoint now keeps a reminder `pending` until
  it ages out of the grace window rather than resolving immediately; it stays
  visible in-app, which is the better failure mode.
- **Operational**: rotating `PUSH_ENCRYPTION_KEY` remains disruptive but is now
  genuinely self-healing as ADR-0020 claimed.
- **Not addressed here**: reminders that age past `REMINDER_GRACE_MINUTES` while
  the process is down are still never delivered. On Render's free tier (instances
  sleep after 15 min idle) this depends on the UptimeRobot keep-alive; see
  `docs/deployment.md`.
