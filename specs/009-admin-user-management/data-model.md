# Phase 1 Data Model — In-App Admin User Management

**One schema change.** This feature adds **one new append-only table, `admin_audit_log`**,
and otherwise reads/writes the existing `users` and `sessions` tables through the reused
domain. One Alembic migration (`just migrate-rev "add admin_audit_log"`); `alembic check` must
report no further drift after it.

## New entity

### AdminAuditLog *(new table — `db/models/admin_audit.py`)*

Append-only record of one successful privileged admin action. Inserted in the **same request
transaction** as the action it describes, so there is exactly one row per successful action
(FR-013/SC-004). Never updated or deleted; no soft-delete.

| Field | Type | Null? | Rule |
|---|---|---|---|
| `id` | UUID PK | no | `uuid_pk()`. |
| `actor_id` | UUID FK → `users.id` | no | The acting admin (from `require_admin`). No cascade. |
| `target_user_id` | UUID FK → `users.id` | no | The affected user. No cascade — survives the target's soft-delete. |
| `action` | ENUM `admin_audit_action` | no | One of `create`, `update`, `role_change`, `password_reset`, `deactivate`. |
| `details` | JSONB | no | Changed **field names** only, e.g. `{"fields": ["name", "email"]}`; `role_change` may carry `{"role": "user→admin"}`. **MUST NOT** contain passwords, hashes, or other secret values. `create`/`password_reset`/`deactivate` may use `{}` or a minimal marker. |
| `created_at` | timestamptz | no | The "when" (`created_at_col()`, server default `now()`). |

**Notes**
- **No `updated_at`, no `deleted_at`** — append-only (FR-022); no in-app path edits or deletes
  rows. Entries are retained indefinitely in this version (no purge job).
- **No success/failure outcome column** — only successful actions are recorded (clarification);
  denied/blocked attempts (non-admin access, blocked last-admin removal) stay in ordinary server
  logs.
- FKs reference `users.id` without `ON DELETE CASCADE`: the project uses soft-delete on `users`,
  and audit history must outlive a deactivated user.
- Register the model in `db/models/__init__.py` so Alembic autogenerate sees the table.
- Default read order for the in-app view (FR-014): `ORDER BY created_at DESC`.

```text
admin_audit_log
├── id              uuid  PK
├── actor_id        uuid  FK → users.id
├── target_user_id  uuid  FK → users.id
├── action          enum  admin_audit_action(create|update|role_change|password_reset|deactivate)
├── details         jsonb {"fields":[...]}  (never secrets)
└── created_at      timestamptz
```

## Entities touched (existing tables — no column changes)

### User *(existing table — `db/models/users.py`)*

No new columns (FR-018 introduces no `must_change_password` flag). Written via the reused
`create_user` / `update_user` / `soft_delete_user` domain functions.

| Field | Touched? | Rule (this feature) |
|---|---|---|
| `id` | read | Path identifier `{user_id}`; resolved via new `get_user_by_id`. |
| `email` | **write** | Set on create; editable on `PATCH`. Case-insensitive unique incl. soft-deleted (existing `update_user` clash check) → 409 on conflict. |
| `password_hash` | **write** | Set on create and on password reset (`update_user(new_password=…)` → also revokes the target's sessions). Plaintext (typed or generated) never stored/logged. |
| `name` | **write** | Display name; 1–100 chars (Pydantic boundary) on create/edit. |
| `role` | **write** | `admin`/`user`; set on create, changeable on edit — guarded so the **last active admin** can't be demoted (`LastAdminError` → 409). |
| `timezone` | write (create only) | Defaults to `UTC` on create; remains user self-service afterward (not edited by the admin UI). |
| `quiet_hours_start/end` | not touched | Self-service / CLI only. |
| `deleted_at` | **write** | Set by deactivate (`soft_delete_user`). Active list filters `deleted_at IS NULL`; no in-app restore (FR-016). |
| `created_at`, `updated_at` | read / auto | `created_at` shown in the list; `updated_at` advances via existing onupdate. |

**Guard query (new):** `count_active_admins(session)` =
`SELECT count(*) FROM users WHERE role = 'admin' AND deleted_at IS NULL` — backs both the
deactivate and the demote last-admin checks (FR-010/SC-006). The deactivate/demote paths take a
`FOR UPDATE` lock on the active-admin rows before counting so the guard holds under concurrent
requests (FR-021) — two simultaneous last-admin removals serialize instead of both passing.

### Session *(existing table — `db/models/sessions.py` / `SessionModel`)*

Not directly modeled here, but **deleted in bulk** by `revoke_all_user_sessions(user_id=target)`
on **password reset** and **deactivation** (FR-007/FR-008/SC-005) — the established ADR-0001
revoke pattern. No new columns.

## Domain functions

**New (this feature):**
- `domain/users.py`: `get_user_by_id(...)`, `count_active_admins(...)`,
  `admin_update_user(...)`, `admin_reset_password(...)`, `admin_deactivate_user(...)`
  (resolve-by-id → guards → reuse `update_user`/`soft_delete_user` → audit write); new errors
  `SelfActionError`, `LastAdminError`.
- `domain/passwords.py`: `generate_temp_password()` (stdlib `secrets`, ≥ 12 chars).
- `domain/audit.py`: `record_admin_action(session, *, actor_id, action, target_user_id, details)`.

**Reused unchanged:** `create_user`, `update_user`, `soft_delete_user`, `list_users`,
`get_user_by_email` (`domain/users.py`); `hash_password`, `password_too_short`
(`domain/passwords.py`); `revoke_all_user_sessions` (`domain/sessions.py`).
