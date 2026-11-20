# MedMinder — Deployment Guide

A beginner-friendly guide to deploying MedMinder on free-tier
infrastructure, with a keep-alive ping so the in-process reminder
scheduler keeps delivering push notifications.

> **This guide reflects the actual production setup**: the app runs on
> **Render's free tier**, kept awake by an external **UptimeRobot** ping;
> Postgres is on **Supabase** free tier. An earlier draft targeted Koyeb —
> abandoned because Koyeb's always-on path now requires a $29/mo plan (its
> free tier force-sleeps). The single-service architecture itself is
> host-agnostic (see ADR-0017), so these steps adapt to any Docker PaaS.

## Architecture overview

MedMinder deploys as a **single service** (ADR-0017): one FastAPI process
serves **both** the JSON API **and** the built React app from the same
origin. Postgres is a managed Supabase instance.

```
┌──────────────────┐     ┌────────────────────────────┐     ┌──────────────────┐
│  Browser / PWA   │────▶│  Render (free web service) │────▶│  Supabase        │
│                  │     │  FastAPI                   │     │  (PostgreSQL)    │
│  UptimeRobot ───▶│     │   ├─ /            → React  │     │                  │
│  (pings /healthz │     │   └─ /api,/auth,  → API    │     │                  │
│   every 5 min)   │     │      /me,/healthz          │     │                  │
└──────────────────┘     └────────────────────────────┘     └──────────────────┘
   One origin              Single instance, kept awake        Free-tier Postgres
                           by the keep-alive ping             (pooler connection)
```

**Why one service?** The session cookie is `SameSite=Lax`, which the
browser only sends on **same-origin** requests. Serving the frontend from
the backend keeps login working with no auth/cookie/CORS changes, and keeps
the service worker's same-origin notification fetches working. See
**ADR-0017** for the rationale and the rejected alternatives
(Vercel/Cloudflare split, `SameSite=None`).

> **The instance must not sleep — and a free instance does.** The in-process
> APScheduler reminder loop (ADR-0002) only delivers push reminders while the
> process is running. Render's free web service sleeps after **15 min idle**.
> We keep it awake with a free **UptimeRobot** monitor that pings `/healthz`
> every **5 minutes** (§2.3). Reminders are reliable *as long as the pinger
> runs*. If you'd rather not depend on a pinger, a paid always-on instance
> (Render Starter ~$7/mo, or Fly.io ~$2–4/mo) removes that dependency.

- **Render free web service**: runs the FastAPI service, built from the
  **root `Dockerfile`** (multi-stage: compiles the React app and bakes it
  into the image). Migrations run on container start (see §1.4).
- **Supabase Free Tier**: managed PostgreSQL, connected directly via
  `asyncpg` over the **transaction pooler** — **not** through Supabase's
  REST or GraphQL APIs.

## What lives where, by phase

| Variable / step | Required from phase | Notes |
|-----------------|---------------------|-------|
| `DATABASE_URL` | Phase 1 | Supabase pooler string, `+asyncpg` form. Percent-encode symbols in the password. Use a DML-only role in hardened mode ([operations.md §2](operations.md#2-hardening-setup-two-database-roles-supabase--render)). |
| `MIGRATION_DATABASE_URL` | Optional (hardening) | Privileged DDL URL used by Alembic and `db backup|restore`. Falls back to `DATABASE_URL` when unset. Keep off Render if `RUN_MIGRATIONS_ON_STARTUP=false`. |
| `RUN_MIGRATIONS_ON_STARTUP` | Optional (hardening) | `true` (default) runs `alembic upgrade head` on container boot; set `false` when running migrations from your workstation with a separate DDL role ([operations.md §1–2](operations.md)). |
| `DATABASE_SSL_MODE` / `DATABASE_SSL_CA_FILE` | Optional (hardening) | Set `verify-full` + `/etc/secrets/supabase-ca.crt` (Render Secret File) to verify Supabase's CA & hostname ([operations.md §3](operations.md#3-hardening-setup-strict-postgresql-tls-verify-full)). |
| `alembic upgrade head` (container entrypoint) | Phase 1 | Runs on each container start before uvicorn unless `RUN_MIGRATIONS_ON_STARTUP=false` (§1.4). |
| `medminder-admin user add` (bootstrap admin) | Phase 1b | Run from your workstation against `DATABASE_URL` (§2.4). |
| `medminder-admin db backup` (scheduled) | Phase 1b | Run from a workstation/cron — see §6 and [operations.md §4](operations.md#4-database-backups--restores). |
| `SESSION_SECRET` | Phase 2 | 32+ random bytes, base64. Signs session cookies. App refuses to boot in prod without it. |
| `TRUSTED_PROXY_COUNT` | Phase 2 | `1` — Render (and its Cloudflare front) add a proxy layer. |
| `CORS_ORIGINS` | Phase 2 | **Omit** — defaults to `[]` (deny-all) outside development; same-origin deploys need no CORS. |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | Phase 7 | Web Push keys; `python scripts/generate_vapid_keys.py`. **Private key is a secret.** |
| `PUSH_ENCRYPTION_KEY` | Phase 10 | Fernet key encrypting push keys at rest (ADR-0020). **App refuses to boot in prod without it.** Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. |
| `REMINDERS_ENABLED` | Phase 7 | `true` in production. **Single instance only** (ADR-0002). |
| `ENV=production` | Always | Disables `/docs` and `/openapi.json`, defaults CORS to deny-all; enables `Secure` cookies, HSTS, `Cache-Control: no-store`, login/password rate-limiting, and CSRF. |

`VITE_API_BASE_URL` is **intentionally empty** in this deploy (the React
app calls relative, same-origin paths). The Dockerfile bakes it as `""` at
build time; you never set it on the host.

---

## Prerequisites

- A [GitHub](https://github.com) account (Render deploys from GitHub).
- The MedMinder repository pushed to GitHub.
- A working local Python env (to bootstrap the first admin and run backups).

---

## 1. Database — Supabase

### 1.1 Create a project

1. Sign up at [supabase.com](https://supabase.com) and create a new project.
2. Choose a region near your app host — for a Render **Virginia** service,
   pick Supabase **East US (North Virginia)** to keep backend↔DB latency low.
3. Set a **strong database password** — you'll need it for the connection
   string. (Disabling the Data API and "automatic RLS" is correct here: we
   connect as raw PostgreSQL and enforce authz in app code, not via RLS.)

### 1.2 Get the connection string

1. **Settings → Database → Connection string → URI**, **Transaction pooler**
   (port `6543`):
   ```
   postgresql://postgres.[ref]:[password]@aws-[n]-[region].pooler.supabase.com:6543/postgres
   ```
2. Convert to the SQLAlchemy `+asyncpg` form (this is your `DATABASE_URL`):
   ```
   postgresql+asyncpg://postgres.[ref]:[password]@aws-[n]-[region].pooler.supabase.com:6543/postgres
   ```
3. **Percent-encode special characters in the password** (`@`→`%40`,
   `$`→`%24`, `*`→`%2A`, `#`→`%23`, etc.). SQLAlchemy decodes them when it
   parses the URL; `alembic/env.py` is written to avoid ConfigParser `%`
   interpolation, so `%`-encoded passwords are safe end to end.

### 1.3 asyncpg + transaction pooler — important

The transaction-mode pooler (port 6543) does **not** support prepared
statements; asyncpg uses them by default. The backend disables them in
`backend/src/medminder/db/__init__.py`:

```python
create_async_engine(
    settings.database_url,
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
)
```

Leave these defaults as-is. By default, asyncpg and psycopg use `ssl=prefer`
(negotiates TLS to Supabase and falls back to plaintext only against local
non-TLS Postgres). For strict CA + hostname verification (`verify-full`), set
`DATABASE_SSL_MODE=verify-full` and `DATABASE_SSL_CA_FILE` — see
[docs/operations.md §3](operations.md#3-hardening-setup-strict-postgresql-tls-verify-full).

### 1.4 Database migrations

Most free PaaS hosts (Render, Koyeb) have **no release / pre-deploy
command**, so by default (`RUN_MIGRATIONS_ON_STARTUP=true`) the production
image runs `alembic upgrade head` in its **entrypoint** on each container
start, *before* uvicorn launches (`set -e` aborts boot if it fails). Safe
because we run a **single** instance and the upgrade is idempotent.

`alembic.ini` omits `sqlalchemy.url`; `alembic/env.py` reads it from
`Settings.database_url_sync` (which prefers `MIGRATION_DATABASE_URL` when set
and otherwise falls back to `DATABASE_URL`, swapped to `+psycopg`) and passes
it straight to SQLAlchemy (never through ConfigParser — that would break on
`%`-encoded passwords).

To keep DDL credentials **completely out** of the Render container, set
`RUN_MIGRATIONS_ON_STARTUP=false` on Render, point `DATABASE_URL` at a
DML-only Postgres role, and run `alembic upgrade head` from your workstation
before deploys with schema changes — step-by-step instructions live in
[docs/operations.md §1–2](operations.md).

### 1.5 Security checklist

- [ ] Use the **pooler connection** (port 6543), not the direct (5432).
- [ ] Don't override the asyncpg prepared-statement settings (§1.3).
- [ ] Never commit the connection string — env vars only.
- [ ] **Two database roles (hardening — §8).** First deploy may use the
      Supabase `postgres` role for both migrations and runtime; splitting
      into a DDL migration role + DML-only runtime role is the first
      hardening task.

---

## 2. App service — Render (one service, frontend + API)

### 2.1 Create the Web Service

1. Sign up at [dashboard.render.com](https://dashboard.render.com) **with
   GitHub** and authorize Render.
2. **Add new → Web Service**, connect the `med-minder` repo, branch `main`.
3. Configure:
   - **Language**: `Docker` (auto-detected from the root `Dockerfile`).
   - **Root Directory**: blank (repo root is the build context).
   - **Dockerfile Path**: `./Dockerfile`.
   - **Region**: `Virginia (US East)` (matches the Supabase `us-east-1` DB).
   - **Instance Type**: `Free` (kept awake by the §2.3 ping). For
     guaranteed always-on without a pinger, use **Starter** (~$7/mo).
   - **Health Check Path**: `/healthz`.
   - **Pre-Deploy Command**: leave **blank** — the image entrypoint migrates.
   - **Auto-Deploy**: On (push to `main` redeploys).
   - Port: nothing to set — Render injects `$PORT` and the image binds it.

> The dev images `backend/Dockerfile` and `frontend/Dockerfile` are for
> local docker-compose only (they run with `--reload`). Production uses the
> **root `Dockerfile`**.

### 2.2 Environment variables

Add under the service's **Environment** section:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://...` (real password, percent-encoded) — §1.2 |
| `SESSION_SECRET` | 32+ random bytes, base64 (`python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(48)).decode())"`) |
| `ENV` | `production` |
| `TRUSTED_PROXY_COUNT` | `1` |
| `REMINDERS_ENABLED` | `true` |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` | from `python scripts/generate_vapid_keys.py` (set `VAPID_SUBJECT` to a real `mailto:`) |
| `PUSH_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` (ADR-0020) |

Generate `SESSION_SECRET`, `PUSH_ENCRYPTION_KEY`, and the VAPID keys **in your
own terminal** and paste the values straight into Render — don't route secrets
through anything
that logs them. Do **not** set `VITE_API_BASE_URL` or `CORS_ORIGINS`.

On Create, Render builds the image (~5–10 min first time), then the
entrypoint runs `alembic upgrade head` against Supabase and launches uvicorn.
The build logs should show `Running upgrade … 0007_admin_audit_log` and
`Uvicorn running`, then the service goes **Live** at
`https://<name>.onrender.com`.

### 2.3 Keep-alive ping (protects reminders)

Render free sleeps after 15 min idle, which stops the scheduler. Keep it up:

1. Sign up free at [uptimerobot.com](https://uptimerobot.com).
2. **New monitor** → Type `HTTP(s)`, URL `https://<name>.onrender.com/healthz`,
   interval **5 minutes**.
3. Create. It pings continuously (and alerts you if the app goes down).

Keep to **one** free Render service to stay within Render's free monthly
instance-hours.

### 2.4 First-admin bootstrap (from your workstation)

Self-registration is forbidden, and Render free has no web shell — so create
the first admin by running the CLI locally against Supabase (tables already
exist after the first deploy migrated them). In **PowerShell**:

```powershell
cd <repo>\backend
$env:DATABASE_URL = "postgresql+asyncpg://postgres.[ref]:[encoded-pw]@aws-[n]-[region].pooler.supabase.com:6543/postgres"
# Sanity-check the URL parsed (prints host/port/user, not the password):
python -c "import os,urllib.parse as u;p=u.urlparse(os.environ['DATABASE_URL']);print(p.hostname,p.port,p.username)"
# Create the admin (12+ char password, piped via stdin):
'YOURPASSWORD' | python -m medminder.cli user add --email you@example.com --name "Your Name" --role admin --password-stdin
```

(bash equivalent: `export DATABASE_URL=... ; echo 'YOURPASSWORD' | medminder-admin user add ...`.)
Success prints the new user's UUID. A transient `getaddrinfo`/DNS error just
means a retry is needed. Subsequent users are managed in-app at
`/admin/users` (ADR-0014).

### 2.5 Verify

```bash
curl https://<name>.onrender.com/healthz   # {"status":"ok"}
```

Then in a browser: open the app, set your timezone in the profile dialog
(click your name), log in, **enable notifications** when prompted, add a
medication with a schedule a couple minutes out, close the tab — you should
get a push. Install the PWA from the browser menu (iOS: Share → Add to Home
Screen).

---

## 3. Frontend

There is **no separate frontend deployment.** The React app is built by the
root `Dockerfile` (Node stage) with `VITE_API_BASE_URL=""` and served by
FastAPI at `/`, with client-side routes falling back to `index.html`
(ADR-0017). Ship a frontend change by pushing to `main`; Render rebuilds.

---

## 4. DNS & HTTPS

Render provides automatic HTTPS on `*.onrender.com`. For a custom domain:
add it to the Render service, update DNS as instructed, redeploy. Because
everything is one origin and `VITE_API_BASE_URL` is empty/relative, **no
special frontend rebuild is needed** for a domain change.

---

## 5. Staging — recommendation

For a free-tier hobby project, skip a separate staging environment: develop
locally against Docker Compose (`just dev`); merges to `main` auto-deploy to
production. When real users depend on it, promote a second free Supabase
project + a second Render service on a `staging` branch. Revisit (and likely
write an ADR) when "would I be embarrassed if a bad migration hit prod?"
becomes "yes."

---

## 6. Backups

Backups use the admin CLI (wraps `pg_dump`/`pg_restore`), run from a
workstation with `DATABASE_URL` set (Render free has no shell):

```bash
medminder-admin db backup --out medminder-$(date -u +%Y%m%dT%H%M%SZ).dump
medminder-admin db restore --in medminder-....dump --yes
```

The dump is `pg_dump --format=custom`. **Treat backup files as protected
health information** — they contain every Argon2id hash and medication
record. For scheduled backups, run the `db backup` command from a machine
you control (e.g. a local cron / Task Scheduler) and push the file to
encrypted, S3-compatible object storage; document the bucket + retention in a
private runbook, not the repo.

---

## 7. Ongoing operations

**Monitoring**: Render dashboard (logs/metrics for the one service),
Supabase dashboard (DB health), UptimeRobot (uptime + alerts).

**Updating**: push to `main` → Render rebuilds the image → the new
container's entrypoint runs `alembic upgrade head`, launches uvicorn, and
Render routes traffic once `/healthz` is healthy.

**Cost**:

| Service | Tier |
|---------|------|
| Supabase | Free: 500 MB DB, 5 GB egress/month |
| Render | Free web service (sleeps after 15 min; kept awake by the ping). Starter ~$7/mo for guaranteed always-on. |
| UptimeRobot | Free (50 monitors, 5-min interval) |

---

## 8. Hardening follow-ups

- **Two database roles (security, NON-NEGOTIABLE per the constitution) —
  supported in code (ADR-0022).** `MIGRATION_DATABASE_URL` and
  `RUN_MIGRATIONS_ON_STARTUP=false` are wired in; follow
  [docs/operations.md §2](operations.md#2-hardening-setup-two-database-roles-supabase--render)
  to create the DML-only `medminder_app` role in Supabase and cut Render over.
- **`verify-full` TLS to Supabase — supported in code (ADR-0022).** Upload
  Supabase's root CA as a Render Secret File (`/etc/secrets/supabase-ca.crt`)
  and set `DATABASE_SSL_MODE=verify-full` + `DATABASE_SSL_CA_FILE` per
  [docs/operations.md §3](operations.md#3-hardening-setup-strict-postgresql-tls-verify-full).
- **Always-on without a pinger** — move to a paid Render Starter or Fly.io
  instance if reminder reliability shouldn't depend on the keep-alive ping.
- **Scheduled off-site encrypted backups** (§6 and [docs/operations.md §4](operations.md#4-database-backups--restores)).
- **Custom domain** (§4).

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Deploy fails at migrations: `invalid interpolation syntax … at position N` | A `%` in the DB password hit ConfigParser. Already fixed in `alembic/env.py` (URL bypasses the config file) — make sure you're on a build that includes that fix. |
| `getaddrinfo failed` running the CLI locally | DNS hiccup or `$env:DATABASE_URL` not set in that shell. Re-run the sanity-check one-liner (§2.4); confirm the host resolves (`nslookup <pooler-host>`). |
| Login succeeds but bounces back to `/login` | Cross-origin cookie problem. This deploy is single-origin to avoid it; confirm the frontend isn't on a different host than the API and `ENV=production` (so cookies are `Secure`). |
| `GET /` returns 404/JSON, not the app | The image didn't bake the frontend / `FRONTEND_DIST` unset. Rebuild from the root `Dockerfile` (it sets `FRONTEND_DIST=/app/frontend_dist`). |
| Reminders stop firing | The instance slept — check the UptimeRobot monitor is up and pinging `/healthz`; check Render didn't suspend the free service for exceeding monthly hours. |
| `prepared statement "..." does not exist` | Hitting the pooler with prepared statements enabled. See §1.3 (don't override the defaults). |
| Build fails | Ensure the build uses the **root** `Dockerfile`, repo root as context; `frontend/pnpm-lock.yaml` and `backend/pyproject.toml` committed. (pnpm is pinned in the Dockerfile to match the lockfile.) |
| App won't start: "SESSION_SECRET must be set…" | `ENV` is non-development but `SESSION_SECRET` is unset/default. Set a strong base64 secret. |
| App won't start: "PUSH_ENCRYPTION_KEY must be set…" | `ENV` is non-development but `PUSH_ENCRYPTION_KEY` is unset/default. Set a unique Fernet key (ADR-0020). |
| Duplicate-email on bootstrap | The admin already exists; `medminder-admin user list --role admin` to confirm. |
