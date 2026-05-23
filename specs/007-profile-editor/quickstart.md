# Quickstart — Self-Service Profile Editor

End-to-end verification of the feature. Assumes the dev stack is up (`just dev`:
Postgres + backend on `:8000` + frontend on `:5173`).

## 0. Provision a user (existing admin CLI)

```bash
echo 'correct horse battery staple' | medminder-admin user add \
    --email molly@example.com --name "Molly" --role user --password-stdin
```

(After this feature ships, this step is also documented in the root `README.md`
Quickstart — FR-016.)

## 1. Manual walkthrough

1. Open `http://localhost:5173`, sign in as `molly@example.com`.
2. **Open the editor**: click **Molly** in the nav bar → the profile modal opens
   (FR-001).
3. **Change the display name** (US2): set name to `Molly R.` and save.
   - The nav bar updates to `Molly R.` without a page reload (FR-008 / SC-004).
   - Empty or > 100-character names are rejected inline (422).
4. **Change the password** (US1): enter the current password and a new one (≥ 12 chars),
   save.
   - A too-short new password is blocked (422); a **wrong current password** shows an
     error on the *current password* field (**403**), and nothing changes (FR-003).
   - On success you stay signed in on this device (FR-005 / SC-003).
5. **Confirm other sessions are revoked**: in a second browser/incognito, sign in as
   Molly *before* step 4. After step 4 succeeds, reload the second session → it is
   bounced to login (its cookie maps to a revoked session). The first device still works.
6. **Forgot-password recovery** (US3): an admin runs
   `echo 'temp-pass-123456' | medminder-admin user update --email molly@example.com --password-stdin`,
   shares it out-of-band; Molly signs in with it and immediately changes it via step 4.
   The temp password no longer works afterward.

## 2. API spot-checks (frontend-bypassing)

```bash
# Log in, capture the cookie jar
curl -sS -c jar.txt -X POST localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"molly@example.com","password":"correct horse battery staple"}'

# Name change → 200, Me reflects new name
curl -sS -b jar.txt -c jar.txt -X PATCH localhost:8000/me \
  -H 'Content-Type: application/json' -d '{"name":"Molly R."}'

# Wrong current password → 403
curl -sS -o /dev/null -w '%{http_code}\n' -b jar.txt -X POST localhost:8000/me/password \
  -H 'Content-Type: application/json' \
  -d '{"current_password":"WRONG","new_password":"brand-new-passw0rd"}'   # → 403

# Too-short new password → 422
curl -sS -o /dev/null -w '%{http_code}\n' -b jar.txt -X POST localhost:8000/me/password \
  -H 'Content-Type: application/json' \
  -d '{"current_password":"correct horse battery staple","new_password":"short"}'  # → 422

# Correct change → 204 + fresh Set-Cookie; the old jar's other sessions are now dead
curl -sS -i -b jar.txt -c jar.txt -X POST localhost:8000/me/password \
  -H 'Content-Type: application/json' \
  -d '{"current_password":"correct horse battery staple","new_password":"brand-new-passw0rd"}'
```

## 3. Automated tests

```bash
# Backend (real Postgres)
cd backend && python -m pytest tests/domain/test_change_own_password.py tests/api/test_me_profile.py -v

# Frontend
cd frontend && pnpm test -- ProfileDialog.test.tsx

# Full gates before PR
just lint && just typecheck && just test
just generate-client   # regenerate api/v1.d.ts; CI fails on drift
```

## Expected results

- `PATCH /me`: 200 + updated `Me.name`; 422 on empty/over-100 name.
- `POST /me/password`: 204 + rotated cookie on success; **403** wrong current password;
  **422** too-short new password; **401** unauthenticated. After success, other sessions
  401 and the current device keeps working.
- Coverage ≥ 85%; `mypy --strict` and `tsc --noEmit` clean; no raw passwords in logs.
