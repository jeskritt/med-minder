# Security Checklist: Reminders + Snooze

**Purpose**: Security merge gate for this phase's new surface — push subscriptions,
reminder endpoints, the in-process scheduler, and Web Push secrets (Constitution
Principle I). Every item must be `[x]` (verified) or `[~]` (PR/CI-runtime, with a link)
before merge.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md) · Decision: [ADR-0002](../../../docs/adr/0002-in-process-apscheduler.md)

## Authentication & authorization

- [x] Every new endpoint requires an authenticated session (push vapid-key,
  subscribe/unsubscribe, reminders list, snooze, dismiss); unauthenticated → **401** —
  `tests/api/test_push_api.py::test_unauthenticated_is_401`,
  `tests/api/test_reminders_api.py::test_unauthenticated_is_401`,
  `tests/api/test_reminders_actions.py::test_unauthenticated_is_401`.
- [x] The VAPID **public** key endpoint is itself auth-gated (nothing served pre-login) —
  `test_push_api.py::test_unauthenticated_is_401`.

## Scope / cross-user isolation (FR-017, SC-008)

- [x] Snooze/dismiss load a reminder by id then assert ownership; another user's reminder
  is **404**, never mutated — `test_reminders_actions.py::test_cross_user_snooze_404`.
- [x] The reminders list returns only the caller's rows —
  `test_reminders_api.py::test_cross_user_isolation`.
- [x] Subscription register/unregister are scoped to the caller; one user's delete cannot
  remove another's subscription — `test_push_api.py::test_delete_does_not_touch_another_users_subscription`.
- [x] Dispatch delivers each user's reminders only to that user's own subscriptions
  (`dispatch_due_reminders` filters subscriptions by `rem.user_id`) —
  `tests/domain/test_reminder_dispatch.py`.

## Secret handling (FR-002, SC-009)

- [x] The VAPID **private** key is configuration/secret only — used solely to sign in
  `domain/push.py`; never sent to the client, returned, or placed in a `PushResult` —
  `tests/domain/test_push.py::test_private_key_never_in_result_repr`. Only the **public**
  key is exposed (`/api/v1/push/vapid-public-key`).
- [x] Subscription secrets (`auth`, `p256dh`) are stored as the existing minimised
  `push_subscriptions` columns and are never logged; push send is best-effort and swallows
  errors without echoing payload/keys (`domain/push.py`).
- [x] Settings carry the private key but it is never logged; `vapid_private_key` empty in
  dev/test → sends are skipped (no accidental use of a placeholder).

## Data minimisation / migration

- [x] **No new tables or columns** and no new PII — `0006_reminder_indexes.py` adds only
  indexes (incl. the `uq_reminders_open_refill` partial-unique). `alembic check` is an
  empty diff (verified, version `0006`, indexes confirmed via `psql`).

## Operational

- [x] The scheduler runs **single-instance** only; horizontal scaling/multiple workers
  would double-deliver — documented in `docs/deployment.md` §2.1 and ADR-0002. It is gated
  by `reminders_enabled` (off in tests/CI/Alembic) so no background loop runs there.
- [x] Push delivery failures are bounded (retry ≤ `reminder_send_max_attempts`) and cannot
  crash the tick; a permanently-gone subscription (404/410) is deleted —
  `tests/domain/test_push_resilience.py`.

## PR

- [~] The PR description includes a **Security considerations** section covering: VAPID
  private-key handling (env-only, never returned/logged), user-scoping of all new
  endpoints with cross-user negatives, the single-instance scheduler requirement, and the
  no-new-PII / indexes-only migration (link on merge).
