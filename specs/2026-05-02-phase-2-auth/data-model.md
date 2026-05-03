# Phase 2 — Data Model

Phase 2 introduces no new tables, columns, indexes, or triggers. Both entities it touches were defined in Phase 1 (`specs/2026-04-29-phase-1-data-model/`) and have the shape Phase 2 needs. **No Alembic migration is anticipated.** This document records how Phase 2 reads and writes the existing entities so reviewers can spot any unintended schema impact in code review.

The authoritative ER diagram is `docs/diagrams/er.md`.

---

## Entity: `User`

**Table**: `users` (Phase 1, `backend/src/medminder/db/models/users.py`)

**Columns Phase 2 reads**:

| Column | Type | Phase 2 use |
|---|---|---|
| `id` | UUID PK | Returned in `GET /me`; written as the FK target on new `sessions` rows; used as the lookup key for `revoke_all_user_sessions` |
| `email` | text, NOT NULL | Lookup target for `domain.users.get_user_by_email` (case-insensitive via the existing `LOWER(email)` functional unique index `ix_users_email_lower`). Email is normalized (lowercase + trimmed) per the spec edge-case section before lookup. |
| `password_hash` | text, NOT NULL | Argon2id hash; passed to `domain.passwords.verify_password`. Phase 2 does not read this directly — `get_user_by_email` returns the row and `verify_password(user.password_hash, plain)` is the only consumer. |
| `name` | text, NOT NULL | Returned in `GET /me`. |
| `role` | enum('admin','user') | Returned in `GET /me`. |
| `deleted_at` | timestamptz NULL | Spec FR-005 — soft-deleted users are treated identically to unknown emails. The lookup uses the existing `include_deleted=False` flag. |

**Columns Phase 2 does not touch**: `timezone`, `quiet_hours_start`, `quiet_hours_end`, `created_at`, `updated_at`. Phase 2 does not modify any column on `users`.

**Validation rules (existing, relevant)**:
- `LOWER(email)` is unique across non-soft-deleted rows (Phase 1 invariant); duplicates are rejected by the index. Phase 2 relies on this for the timing-uniform behavior in FR-004 — there is exactly zero or one matching user per (lowercased) email.

**State transitions**: Phase 2 introduces no state transitions on `users`. Soft-delete remains a Phase 1 / CLI concern; Phase 2 only reads `deleted_at`.

---

## Entity: `Session`

**Table**: `sessions` (Phase 1, `backend/src/medminder/db/models/sessions.py`)

**Schema (existing)**:

| Column | Type | Phase 2 use |
|---|---|---|
| `id` | UUID PK | Server-generated via `gen_random_uuid()`. Not exposed to the client. |
| `user_id` | UUID FK → `users.id` ON DELETE CASCADE, indexed | Set on `INSERT` from the authenticated user. The CASCADE handles hard-delete of users; soft-delete is handled by the explicit `revoke_all_user_sessions` call (D10). |
| `token_hash` | text, NOT NULL, UNIQUE | SHA-256 hex of the high-entropy plaintext token (D2). Lookup index for `authenticate_token`. The plaintext token is never persisted. |
| `expires_at` | timestamptz, NOT NULL | Server-authoritative session expiry. Mutated in place on every successful authenticated request to extend the rolling window (D4). |
| `created_at` | timestamptz, NOT NULL, default `now()` | Set by the database on `INSERT`. Read-only thereafter. |

**Phase 2 mutations**:
- `INSERT` on login success.
- `UPDATE … SET expires_at = now() + interval '30 days' WHERE id = …` on every authenticated request that passes the validity check (rolling expiry, FR-009).
- `DELETE WHERE token_hash = $1` on logout.
- `DELETE WHERE user_id = $1` on admin password change (FR-010) or soft-delete (FR-011), via `revoke_all_user_sessions`.
- `DELETE WHERE token_hash = $cookie_token_hash` *before* creating a new row when a login is submitted with an existing cookie present (FR-016).

**Validation rules**:
- `token_hash` UNIQUE — collision is implausible given 256-bit token entropy, but the constraint defends against bugs (e.g. a future copy-paste that re-inserts a row).
- `expires_at` is always in the future at the moment a row is read; if a request finds `expires_at <= now()`, the auth dependency returns 401 and explicitly leaves the row untouched (FR-007 + spec edge case).

**State transitions** (per row):

```
   (none)
     │  INSERT on login success
     ▼
  active  ── UPDATE expires_at on each authenticated request ──┐
     │                                                          │
     │  DELETE on logout / admin password change /              │
     │  admin soft-delete / FR-016 re-login / row's             │
     │  expires_at < now() AND a cleanup job collects it        │
     ▼                                                          │
  (gone) ◄──────────────────────────────────────────────────────┘
```

There is no "expired but present" terminal state in code paths — when `expires_at` is in the past, the auth dependency rejects the request and the row is left as-is until a future cleanup phase. Phase 2 does not introduce a cleanup job; Phase 10 (Hardening) will.

**Concurrency notes**:
- Two concurrent authenticated requests on the same session both run the rolling-expiry `UPDATE`. The last writer wins; both extensions are by the same delta, so the final `expires_at` is correct regardless of order.
- Concurrent logout from two tabs: the first `DELETE` removes the row; the second is a no-op. Both return 204 No Content (idempotent — FR-006).

---

## Entities introduced by Phase 2: none

Phase 2 introduces no new persistent entities. The two transient values it produces — the plaintext session token and the signed cookie — exist only on the wire.

## Schema-change impact on Alembic and CI

- No new migration file is added under `backend/alembic/versions/`.
- The CI gate that runs `alembic upgrade head` followed by `alembic check` continues to pass with no new revision.
- The OpenAPI-drift gate is the only CI gate that should change behavior in this phase: the regenerated `frontend/src/api/v1.d.ts` will include the three new endpoints.

## Open questions: none

Every spec assumption that touched the data model was settled by D4 (rolling expiry mutates `expires_at`, no `last_seen_at` column).
