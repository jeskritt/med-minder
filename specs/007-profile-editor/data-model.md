# Phase 1 Data Model — Self-Service Profile Editor

**No schema change.** This feature mutates two columns on the existing `users` table and
deletes/inserts rows in the existing `sessions` table. No new tables, no new columns, **no
Alembic migration** — `alembic check` reports no drift because no model changes.

## Entities touched

### User *(existing table — `db/models/users.py`)*

Only two columns are written by this feature; everything else is read-only here.

| Field | Type | Touched? | Rule (this feature) |
|---|---|---|---|
| `id` | UUID PK | read | Identifies the authenticated user (from the session). |
| `email` | TEXT, `LOWER(email)` unique | **not touched** | Login credential; admin-managed only (FR-010). Never editable via the self-service surface. |
| `password_hash` | TEXT (Argon2id) | **write** | Replaced by `hash_password(new_password)` after the current password verifies and the new password passes the 12-char minimum. |
| `name` | TEXT | **write** | Display name. Required, trimmed, **1–100 characters** (Pydantic `ProfileUpdate`). |
| `role` | ENUM(admin,user) | not touched | — |
| `timezone`, `quiet_hours_*` | TEXT / TIME | not touched | — |
| `deleted_at` | timestamptz \| null | read | Soft-deleted users never authenticate, so they never reach these endpoints. |
| `created_at`, `updated_at` | timestamptz | auto | `updated_at` advances via the existing onupdate. |

**Validation rules**
- `name`: `str`, trimmed, length 1–100; whitespace-only rejected → **422**.
- `new_password`: length ≥ `MIN_PASSWORD_LENGTH` (12) enforced by
  `domain.passwords.password_too_short` → **422** on failure. Bounded `max_length=1024`
  at the boundary.
- `current_password`: must verify against `password_hash` via `verify_password` → **403**
  on mismatch (never 401).

### Session *(existing table — `db/models/sessions.py` / `SessionModel`)*

| Field | Type | Touched? | Rule (this feature) |
|---|---|---|---|
| `id` | UUID PK | insert | New row minted on password change (re-issue). |
| `user_id` | UUID FK → users | read/write | Scope for the bulk delete and the new row. |
| `token_hash` | TEXT (SHA-256) | insert | Hash of the freshly minted token; plaintext only on the wire/cookie. |
| `expires_at` | timestamptz | insert | `now + SESSION_LIFETIME` (30 days). |

**State transition — on a successful `POST /me/password`**

```
verify current password ──ok──▶ set new password_hash ──▶ DELETE all sessions WHERE user_id = me
                                                              │
                                                              ▼
                                              INSERT one fresh session (current device)
                                                              │
                                                              ▼
                                              Set-Cookie: mm_session=<new signed token>
```

Net effect: every prior session for the user (including the one the request arrived on)
is gone; the current device holds a brand-new, rotated session. Other devices' cookies
now map to no row → their next request is a 401.

A name change (`PATCH /me`) performs **no** session mutation.

## Reused domain functions (no new persistence code)

- `domain/passwords.py`: `verify_password`, `password_too_short`, `hash_password`.
- `domain/sessions.py`: `revoke_all_user_sessions`, `create_session`, `hash_token`.
- `domain/users.py`: `update_user` (name path) + **new** `change_own_password`
  (orchestrates verify → set hash → flush → `revoke_all_user_sessions`) and **new**
  `IncorrectPasswordError`.
