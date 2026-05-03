# Phase 2 — Quickstart

Minimal end-to-end flow that exercises every Phase 2 acceptance scenario at the lowest level needed to be convincing. Use this as both an onboarding guide for a developer who lands on the branch fresh and as the manual smoke test before pushing the PR.

## Prerequisites

- Docker Desktop running.
- The repository checked out on branch `phase-2-auth`.
- Either Git Bash / WSL (the `justfile` uses bash). PowerShell-only environments should call the underlying commands directly.

## 0. Bring up the stack

```bash
just dev          # docker compose up --build — Postgres 17 + backend + frontend
just migrate      # alembic upgrade head — should be a no-op in this phase
```

The frontend is now at `http://localhost:5173` and the backend at `http://localhost:8000`. The dev proxy maps `/api/*` on the frontend to `*` on the backend; `/api/healthz` should return `{"status":"ok"}`.

## 1. Provision a user via the admin CLI

```bash
docker compose exec backend bash -lc '
  echo "correcthorsebatterystaple" | medminder-admin user add \
    --email alice@example.com \
    --name "Alice Example" \
    --role user \
    --password-stdin
'
```

The CLI prints the new user's UUID. Take note of it — Story 5 and 6 refer to it.

## 2. Story 1 — Successful login

In the browser, navigate to `http://localhost:5173/login`. Submit:

- Email: `alice@example.com`
- Password: `correcthorsebatterystaple`

Expected:
- The browser is redirected to `/medications`. The page renders a placeholder ("Phase 3 will populate this").
- DevTools → Application → Cookies shows `mm_session` with `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` ≈ 30 d. In production builds it also has `Secure`.
- DevTools → Network shows `GET /api/me` returning `200` with `{ id, name, role }`.

Backend log shows exactly one INFO line per attempt with `outcome=success`, the user's `user_id`, the source IP, and the user agent. **No email, password, or token material appears in the line.**

## 3. Story 4 — Auth-required route guards

Open a Private/Incognito window and navigate to `http://localhost:5173/medications`. You should be redirected to `/login`.

From a terminal:
```bash
curl -i http://localhost:8000/me
# → 401, body { "detail": "Not authenticated" } or equivalent generic
curl -i --cookie "mm_session=garbled" http://localhost:8000/me
# → 401, identical to the no-cookie case
```

## 4. Story 3 — Failed login is timing-safe and uniform

Submit each of:
- Wrong password (`alice@example.com` + `nope`)
- Unknown email (`nobody@example.com` + anything)
- Soft-deleted user — first run `medminder-admin user delete --email alice@example.com` then retry login with the original password.

All three should produce the same generic error body and a comparable response time (the server runs Argon2id on every path; the wall-clock delta should be well under 50 ms in steady state). After the first soft-deleted attempt, restore the user with a fresh `user add` if you want to continue.

## 5. Story 2 — Logout

Click the "Logout" button on the `/medications` page (after re-creating Alice and re-logging in). Expected:
- The browser lands on `/login`.
- DevTools shows the `mm_session` cookie is cleared.
- `curl -i http://localhost:8000/me` with the now-stale cookie returns `401`.
- A second logout (replay the same `POST /api/auth/logout`) succeeds with `204`.

## 6. Stories 5 & 6 — Forced logout on admin password change / soft-delete

Log in as Alice in browser A, leave it on `/medications`. Then:

```bash
# Force password change
docker compose exec backend bash -lc '
  echo "freshfreshfresh!!" | medminder-admin user update \
    --email alice@example.com --password-stdin
'
```

Switch back to browser A and refresh `/medications`. Expected:
- Browser A is redirected to `/login`. All `sessions` rows for Alice have been deleted in the same transaction as the password change.

Re-login with the new password, then:

```bash
docker compose exec backend bash -lc '
  medminder-admin user delete --email alice@example.com
'
```

Refresh browser A: redirected to `/login`. Attempt to log in again as Alice: receive the same generic error as for an unknown email (Story 6).

## 7. Story 7 — Rolling 30-day expiry (automated only)

Manual verification of a 30-day window is impractical. The automated check uses `freezegun` and lives in `backend/tests/api/test_rolling_expiry.py`:

```python
# Sketch — see the actual test for the full setup.
import freezegun

@pytest.mark.asyncio
async def test_rolling_expiry_extends_at_29_days(client, alice_session_cookie):
    initial_expiry = await fetch_session_expiry(...)
    with freezegun.freeze_time(initial_expiry - timedelta(days=1)):
        r = await client.get("/me", cookies={"mm_session": alice_session_cookie})
        assert r.status_code == 200
    new_expiry = await fetch_session_expiry(...)
    assert new_expiry > initial_expiry  # extended

@pytest.mark.asyncio
async def test_expired_session_is_rejected(client, alice_session_cookie):
    initial_expiry = await fetch_session_expiry(...)
    with freezegun.freeze_time(initial_expiry + timedelta(days=1)):
        r = await client.get("/me", cookies={"mm_session": alice_session_cookie})
        assert r.status_code == 401
    after = await fetch_session_expiry(...)
    assert after == initial_expiry  # NOT extended
```

Run `just test` (or `cd backend && python -m pytest tests/api/test_rolling_expiry.py -v`).

## 8. Verifying the FR-019 logging shape

While exercising any of the login flows above, tail the backend log:

```bash
docker compose logs -f backend | grep -E "auth\.login"
```

Expected: one line per attempt; structured fields cover `outcome`, `user_id` (or `null`), `source_ip`, `user_agent`. `grep -iE 'password|email|token|hash'` on the same stream should produce **zero hits** (SC-006).

## 9. Tear down

```bash
just dev-down
```

## What "done" looks like

When all eight steps above produce the expected behavior **and** `just test`, `just lint`, `just typecheck`, and `just generate-client` (followed by `git diff --exit-code -- frontend/src/api/v1.d.ts`) all pass cleanly, Phase 2 is ready for `/speckit-tasks` to close out and merge.
