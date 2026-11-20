# MedMinder — Operations Guide

Day-2 runbook for operating MedMinder on **Render + Supabase**. For initial
setup from scratch, start with [docs/deployment.md](deployment.md).

---

## 1. Routine Deploys

How you deploy depends on whether you have enabled hardened two-role mode
(`RUN_MIGRATIONS_ON_STARTUP=false`, see §2):

### Standard mode (`RUN_MIGRATIONS_ON_STARTUP=true`, default)

1. Merge your PR into `main`.
2. Render rebuilds the root `Dockerfile`, runs `alembic upgrade head` on
   startup, and boots `uvicorn`.
3. Verify `https://<your-app>.onrender.com/healthz` returns `{"status":"ok"}`.

### Hardened two-role mode (`RUN_MIGRATIONS_ON_STARTUP=false`, recommended)

In this mode, Render holds **only** the DML-only `DATABASE_URL` and never sees
DDL credentials.

- **Code-only deploy (no new file under `backend/alembic/versions/`):**
  Just merge to `main`. Render builds and restarts automatically.
- **Deploy with a new database migration:**
  1. **Run the migration first** from your workstation using your privileged
     `MIGRATION_DATABASE_URL` (stored in your password manager, never on
     Render):

     **PowerShell (Windows):**
     ```powershell
     cd backend
     $env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://postgres.<ref>:<encoded-pw>@aws-<n>-<region>.pooler.supabase.com:6543/postgres"
     $env:DATABASE_SSL_MODE = "verify-full"
     $env:DATABASE_SSL_CA_FILE = "C:\path\to\prod-ca-2021.crt"

     uv run --frozen alembic current
     uv run --frozen alembic upgrade head
     uv run --frozen alembic current
     ```

     **bash (Linux / macOS / Git Bash):**
     ```bash
     cd backend
     export MIGRATION_DATABASE_URL="postgresql+asyncpg://postgres.<ref>:<encoded-pw>@aws-<n>-<region>.pooler.supabase.com:6543/postgres"
     export DATABASE_SSL_MODE="verify-full"
     export DATABASE_SSL_CA_FILE="/path/to/prod-ca-2021.crt"

     uv run --frozen alembic current
     uv run --frozen alembic upgrade head
     uv run --frozen alembic current
     ```

     *(Alembic prefers `MIGRATION_DATABASE_URL` over `DATABASE_URL`. Because
     all MedMinder migrations are forward-compatible with the currently running
     app or quick additive changes, running `upgrade head` right before merging
     keeps downtime near zero.)*
  2. Merge to `main` (or trigger a Render deploy). Render boots `uvicorn`
     without running Alembic.
  3. Clear the privileged env var from your shell when done:
     `Remove-Item Env:MIGRATION_DATABASE_URL` (PowerShell) or
     `unset MIGRATION_DATABASE_URL` (bash).

---

## 2. Hardening Setup: Two Database Roles (Supabase + Render)

Separating DDL (`postgres`) from DML (`medminder_app`) ensures that even if an
application bug occurred, the runtime process cannot drop tables, alter schema,
or modify database roles.

### Step 1 — Create the DML-only role in Supabase

Open **Supabase Dashboard → SQL Editor** and run (replace
`CHANGE_ME_STRONG_PASSWORD` with a fresh random password):

```sql
-- 1. Create the least-privilege runtime role
CREATE ROLE medminder_app LOGIN PASSWORD 'CHANGE_ME_STRONG_PASSWORD';

-- 2. Allow using the public schema, but NOT creating objects in it
GRANT USAGE ON SCHEMA public TO medminder_app;
REVOKE CREATE ON SCHEMA public FROM medminder_app;

-- 3. Grant DML on all existing tables and sequences
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO medminder_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO medminder_app;

-- 4. Keep Alembic's version table read-only for the runtime role
REVOKE INSERT, UPDATE, DELETE ON TABLE public.alembic_version FROM medminder_app;

-- 5. Automatically grant DML on future tables/sequences created by migrations
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO medminder_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO medminder_app;
```

### Step 2 — Build the new runtime `DATABASE_URL`

Supabase's transaction pooler (port `6543`) requires `<role>.<project-ref>` as
the username:

```text
postgresql+asyncpg://medminder_app.<project-ref>:<url-encoded-password>@aws-<n>-<region>.pooler.supabase.com:6543/postgres
```

Percent-encode any special characters in the password (`@`→`%40`, `$`→`%24`,
`#`→`%23`, `%`→`%25`, etc.).

### Step 3 — Verify from your workstation before cutting over Render

```powershell
cd backend
$env:DATABASE_URL = "postgresql+asyncpg://medminder_app.<ref>:<encoded-pw>@aws-<n>-<region>.pooler.supabase.com:6543/postgres"
# Should list users cleanly (DML works):
uv run --frozen medminder-admin user list
```

### Step 4 — Update Render Environment Variables

In **Render Dashboard → your service → Environment**:

1. Update `DATABASE_URL` to the `medminder_app.<ref>` connection string.
2. Add `RUN_MIGRATIONS_ON_STARTUP` = `false`.
3. Do **not** set `MIGRATION_DATABASE_URL` on Render (keep it in your password
   manager for workstation migrations in §1).
4. Save changes (triggers a redeploy) and verify `/healthz` and login work.

> **Alternative if you want Render to keep auto-migrating:** You can leave
> `RUN_MIGRATIONS_ON_STARTUP=true` and set *both* `DATABASE_URL` (DML-only) and
> `MIGRATION_DATABASE_URL` (DDL) on Render. That still isolates Uvicorn's
> connection pool to DML-only, though keeping `RUN_MIGRATIONS_ON_STARTUP=false`
> is stronger because DDL credentials never exist inside the runtime container.

---

## 3. Hardening Setup: Strict PostgreSQL TLS (`verify-full`)

By default, `asyncpg` and `psycopg` use `ssl=prefer`. To prevent TLS downgrade
or MITM attacks against Supabase:

### Step 1 — Download Supabase's Root CA certificate

1. In **Supabase Dashboard → Project Settings → Database → SSL Configuration**,
   download the SSL certificate (`prod-ca-2021.crt`).

### Step 2 — Mount it as a Secret File on Render

1. Go to **Render Dashboard → your service → Environment → Secret Files**.
2. Click **+ Add Secret File**:
   - **Filename:** `supabase-ca.crt`
   - **Contents:** paste the full PEM contents of `prod-ca-2021.crt`.
3. Render mounts Secret Files at `/etc/secrets/supabase-ca.crt` (the production
   `Dockerfile` runs as `appuser` with UID/GID `1000` so `/etc/secrets/*` is
   readable without root).

### Step 3 — Enable `verify-full` on Render

In **Render Dashboard → your service → Environment**, add:

| Variable | Value |
|----------|-------|
| `DATABASE_SSL_MODE` | `verify-full` |
| `DATABASE_SSL_CA_FILE` | `/etc/secrets/supabase-ca.crt` |

Save changes to redeploy and check Render logs for a clean startup with no TLS
errors.

*(If you run `alembic` or `medminder-admin` locally against Supabase, set the
same two variables pointing at your local copy of `prod-ca-2021.crt`.)*

---

## 4. Database Backups & Restores

`medminder-admin db backup` and `db restore` shell out to `pg_dump` /
`pg_restore`, pass credentials via `PG*` env vars (never argv), prefer
`MIGRATION_DATABASE_URL` when set, and automatically honour
`DATABASE_SSL_MODE` / `DATABASE_SSL_CA_FILE`.

### Create a backup

**PowerShell:**
```powershell
cd backend
$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://postgres.<ref>:<encoded-pw>@aws-<n>-<region>.pooler.supabase.com:6543/postgres"
$env:DATABASE_SSL_MODE = "verify-full"
$env:DATABASE_SSL_CA_FILE = "C:\path\to\prod-ca-2021.crt"

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
uv run --frozen medminder-admin db backup --out "medminder-$stamp.dump"
# Restrict NTFS ACL on Windows so only your user can read the dump:
icacls "medminder-$stamp.dump" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"
```

**bash:**
```bash
cd backend
export MIGRATION_DATABASE_URL="postgresql+asyncpg://postgres.<ref>:<encoded-pw>@aws-<n>-<region>.pooler.supabase.com:6543/postgres"
export DATABASE_SSL_MODE="verify-full"
export DATABASE_SSL_CA_FILE="/path/to/prod-ca-2021.crt"

uv run --frozen medminder-admin db backup --out "medminder-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

> **Treat `.dump` files as protected health information** — they contain all
> medication records and Argon2id password hashes. Store encrypted off-site and
> delete local copies once archived.

### Restore a backup

Restore requires DDL (`pg_restore --clean --if-exists`), so use
`MIGRATION_DATABASE_URL`:

```bash
uv run --frozen medminder-admin db restore --in medminder-20261120T120000Z.dump --yes
```

---

## 5. User & Secret Operations

### Admin user management (from workstation)

Run with `DATABASE_URL` (the DML-only role is sufficient):

```powershell
# Add an admin or standard user (password piped via stdin, 12+ chars):
'a strong passphrase 12+ chars' | uv run --frozen medminder-admin user add `
    --email user@example.com --name "Name" --role admin --password-stdin

# List users:
uv run --frozen medminder-admin user list
```

### Rotating secrets on Render

| Secret | How to generate | User impact on rotation |
|--------|-----------------|-------------------------|
| `SESSION_SECRET` | `python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(48)).decode())"` | Immediately invalidates all active browser sessions (everyone logs in again). |
| `PUSH_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` | Existing push rows fail decryption and are dropped on the next tick; browsers automatically re-sync on next app open (ADR-0021). |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | `python scripts/generate_vapid_keys.py` | Existing browser push subscriptions become invalid; users re-enable notifications once. |
| DB role passwords | Change in Supabase, then update `DATABASE_URL` on Render (and password manager for `MIGRATION_DATABASE_URL`). | Brief reconnect during Render restart. |

---

## 6. Dependency & Lockfile Maintenance

Both backend (`backend/uv.lock`) and frontend (`frontend/pnpm-lock.yaml`) are
locked and audited in CI (`pip-audit` + `pnpm audit --audit-level high`).

- **Update backend lockfile** (e.g. after a security advisory or editing `backend/pyproject.toml`):
  ```bash
  cd backend
  uv lock --upgrade        # or `uv lock --upgrade-package <name>`
  uv sync --frozen --extra dev
  ```
- **Update frontend lockfile:**
  ```bash
  cd frontend
  pnpm update
  pnpm audit --prod
  ```
- **Regenerate OpenAPI types** whenever backend API schemas or route docstrings change:
  ```bash
  uv run --project backend --frozen python scripts/generate_openapi_client.py
  ```

---

## 7. Health & Troubleshooting Quick Checks

- **App health:** `curl https://<your-app>.onrender.com/healthz` → `{"status":"ok"}`.
- **Reminders stopped firing:**
  1. Check **UptimeRobot** — Render Free sleeps after 15 min idle if the 5-min `/healthz` ping stops.
  2. Check **Render Logs** for scheduler tick lines (`due/dispatched/failed/subs_dropped`) or VAPID/TLS errors.
- **Timezone rule changed (e.g. regional DST abolition):** After deploying updated `tzdata`, toggle your timezone in Profile once (e.g. `UTC` → Save → your zone → Save) to immediately regenerate pre-materialised pending reminders.
- **Container fails to read `/etc/secrets/supabase-ca.crt`:** Verify you are on an image built with `appuser` UID/GID `1000` (see root `Dockerfile`) and that the Secret File name matches `DATABASE_SSL_CA_FILE`.
