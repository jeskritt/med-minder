# Quickstart — In-App Admin User Management

End-to-end verification of the feature. Assumes the dev stack is up (`just dev`:
Postgres + backend on `:8000` + frontend on `:5173`) and the migration has been applied
(`just migrate`).

## 0. Provision an admin (existing CLI — bootstrap only)

```bash
echo 'correct horse battery staple' | medminder-admin user add \
    --email boss@example.com --name "Boss" --role admin --password-stdin
```

After this feature ships, every *subsequent* user is created in-app — this CLI step is only
the one-time bootstrap admin (the hosting one-shot job is no longer needed for routine work).

## 1. Manual walkthrough

1. Open `http://localhost:5173`, sign in as `boss@example.com`.
2. **Admin link** (FR-015): an **Admin** link appears in the nav bar (it does **not** appear
   for `role=user` accounts). Click it → the `/admin/users` page.
3. **List** (US1): the page lists active users with email, name, role, created date. Your own
   row shows but its Edit / Reset / Deactivate actions are **disabled** with a hint pointing to
   the profile editor (FR-019).
4. **Create — typed** (US1): "Add user" → email `dan@example.com`, name `Dan`, role `user`,
   type a password ≥ 12 chars → save → Dan appears in the list. Sign out, sign in as Dan to
   confirm.
5. **Create — generated** (US1): "Add user" → `molly@example.com`, choose **Generate
   password** → save → a one-time temporary password is shown with a copy button and a
   "won't be shown again" note. Relay it; Molly signs in and can later rotate it in the
   profile editor (voluntary — no forced change, FR-018).
6. **Edit** (US2): edit Dan → change role to `admin`, change name → save (200). Try changing
   Dan's email to `boss@example.com` → rejected (409, email exists).
7. **Reset password** (US2): reset Molly's password (typed or generated) → her existing
   sessions are revoked (a second logged-in Molly session is bounced to login on its next
   request).
8. **Deactivate** (US3): deactivate Dan via the **in-app confirm modal** → he disappears from
   the list and can no longer sign in; his sessions are revoked.
9. **Guards** (SC-006): your own row can't be deactivated (action disabled / 403). With only
   one admin left, attempting to deactivate or demote that admin is refused (409).
10. **Audit** (US4/P3): open the audit view → entries for the create/edit/reset/deactivate
    above appear newest-first, attributing each to `boss@example.com`; no passwords are shown.

## 2. API spot-checks (frontend-bypassing)

```bash
# Sign in as the admin, capture the cookie jar
curl -sS -c jar.txt -X POST localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"boss@example.com","password":"correct horse battery staple"}'

# List active users → 200
curl -sS -b jar.txt localhost:8000/api/v1/users

# Create with a generated password → 201 + temporary_password (once)
curl -sS -b jar.txt -X POST localhost:8000/api/v1/users \
  -H 'Content-Type: application/json' \
  -d '{"email":"molly@example.com","name":"Molly","role":"user","generate":true}'

# Both password AND generate → 422 (exactly one allowed)
curl -sS -o /dev/null -w '%{http_code}\n' -b jar.txt -X POST localhost:8000/api/v1/users \
  -H 'Content-Type: application/json' \
  -d '{"email":"x@example.com","name":"X","role":"user","password":"abcdefgh0123","generate":true}'  # → 422

# A NON-admin gets 403 on the same endpoint (sign in as molly first into jar2.txt) → 403
curl -sS -o /dev/null -w '%{http_code}\n' -b jar2.txt localhost:8000/api/v1/users   # → 403

# Editing your own account here → 403 (use the profile editor)
curl -sS -o /dev/null -w '%{http_code}\n' -b jar.txt -X PATCH localhost:8000/api/v1/users/<own-id> \
  -H 'Content-Type: application/json' -d '{"name":"Boss R."}'   # → 403

# Deactivate → 204; sole-admin deactivate → 409
curl -sS -o /dev/null -w '%{http_code}\n' -b jar.txt -X DELETE localhost:8000/api/v1/users/<dan-id>  # → 204
```

## 3. Automated tests

```bash
# Backend (real Postgres)
cd backend && python -m pytest tests/domain/test_admin_guards.py tests/api/test_users_create.py \
  tests/api/test_users_admin_access.py -v

# Frontend
cd frontend && pnpm test -- AdminUsers.test.tsx

# Full gates before PR
just migrate            # apply the admin_audit_log migration locally
just lint && just typecheck && just test
just generate-client    # regenerate api/v1.d.ts; CI fails on drift
# CI also runs: alembic upgrade head && alembic check (no drift after the new migration)
```

## Expected results

- `GET /api/v1/users`: 200 (active only) for admins; **403** for non-admins; **401**
  unauthenticated.
- `POST /api/v1/users`: 201; `temporary_password` present once when `generate=true`; **409**
  duplicate email; **422** short typed password or both/neither password+generate.
- `PATCH /api/v1/users/{id}`: 200; **403** editing self; **409** email conflict or demoting the
  last admin; **422** empty/unknown field.
- `POST /api/v1/users/{id}/password`: 200; revokes the target's sessions; **403** on self.
- `DELETE /api/v1/users/{id}`: 204 + sessions revoked; **403** self; **409** last admin.
- Exactly one `admin_audit_log` row per successful action, attributable to the actor, with no
  secret values; audit list is newest-first.
- Coverage ≥ 85%; `mypy --strict` and `tsc --noEmit` clean; `alembic check` clean; no raw
  passwords / hashes / emails in logs.
