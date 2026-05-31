# MedMinder — Deployment Guide

A beginner-friendly guide to deploying MedMinder using free-tier
infrastructure. This setup keeps background timers (APScheduler) alive
and avoids container-sleep limitations.

## Architecture overview

MedMinder deploys as a **single service** (see ADR-0017): one FastAPI
process serves **both** the JSON API **and** the built React app from the
same origin. Postgres is a managed Supabase instance.

```
┌──────────────────┐     ┌────────────────────────────┐     ┌──────────────────┐
│                  │     │  Koyeb (Eco Micro)         │     │                  │
│  Browser / PWA   │────▶│  FastAPI                   │────▶│  Supabase        │
│                  │     │   ├─ /            → React  │     │  (PostgreSQL)    │
│                  │     │   └─ /api,/auth,  → API    │     │                  │
│                  │     │      /me,/healthz          │     │                  │
└──────────────────┘     └────────────────────────────┘     └──────────────────┘
   One origin              Single no-sleep instance           Free-tier Postgres
                           (serves SPA + API)                 (pooler connection)
```

**Why one service?** The session cookie is `SameSite=Lax`, which the
browser only sends on **same-origin** requests. Serving the frontend from
the backend keeps login working with no auth/cookie/CORS changes, keeps the
service worker's same-origin notification fetches working, and runs on one
Koyeb Eco Micro instance that **does not sleep** — required so the
in-process APScheduler reminder loop (ADR-0002) keeps delivering push
reminders. See **ADR-0017** for the full rationale and the alternatives
(Vercel/Cloudflare split, `SameSite=None`) that were rejected.

- **Koyeb Free Tier (Eco Micro, no sleep)**: runs the FastAPI service,
  built from the **root `Dockerfile`** (multi-stage: it compiles the React
  app and bakes it into the image).
- **Supabase Free Tier**: managed PostgreSQL, connected directly via
  `asyncpg` over the **transaction pooler** — **not** through Supabase's
  REST or GraphQL APIs.

## What lives where, by phase

The deployment doesn't change shape between phases, but the set of
required environment variables and migrations grows:

| Variable / step | Required from phase | Notes |
|-----------------|---------------------|-------|
| `DATABASE_URL` | Phase 1 | Supabase connection string (`+asyncpg`, pooler). |
| `alembic upgrade head` (release command) | Phase 1 | Runs once per deploy before traffic. |
| `medminder-admin user add` (bootstrap admin) | Phase 1b | One-shot Koyeb job after first deploy. |
| `medminder-admin db backup` (scheduled) | Phase 1b | One-shot or cron job — see §6. |
| `SESSION_SECRET` | Phase 2 | 32+ random bytes, base64. Signs session cookies. App refuses to boot in prod without it. |
| `CORS_ORIGINS` | Phase 2 | Same-origin in this deploy, so not load-bearing; set to your app URL anyway. |
| `TRUSTED_PROXY_COUNT` | Phase 2 | `1` — Koyeb adds one proxy layer in front of the app. |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | Phase 7 | Web Push keys; generate with `python scripts/generate_vapid_keys.py`. **Private key is a secret** — env-only, never logged or returned. |
| `REMINDERS_ENABLED` | Phase 7 | `true` in production (starts the in-process reminder scheduler). **Single instance only** — see §2.1. |
| `ENV=production` | Always | Disables permissive dev CORS, dev `/docs`, and dev-only diagnostics; enables `Secure` cookies. |

`VITE_API_BASE_URL` is **intentionally empty** in this deploy (the React
app calls relative, same-origin paths). The Dockerfile sets it to `""` at
build time; you do not configure it on Koyeb.

When you complete a phase, remove the "from phase X" comment for the
variables it introduces, since they become baseline.

---

## Prerequisites

- A [GitHub](https://github.com) account (Koyeb deploys from GitHub).
- The MedMinder repository pushed to GitHub.

---

## 1. Database — Supabase

### 1.1 Create a project

1. Sign up at [supabase.com](https://supabase.com) and create a new
   project.
2. Choose a region close to your Koyeb deployment (see §2).
3. Set a **strong database password** — you'll need it for the
   connection string.

### 1.2 Get the connection string

1. Go to **Settings → Database** in the Supabase dashboard.
2. Under **Connection string → URI**, copy the **transaction pooler**
   string (port `6543`):
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```
3. Convert it to the SQLAlchemy `+asyncpg` form (this is your
   `DATABASE_URL`):
   ```
   postgresql+asyncpg://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```

### 1.3 asyncpg + transaction pooler — important

Supabase's transaction-mode pooler (port 6543) does **not** support
prepared statements. asyncpg uses prepared statements by default; if
you don't disable them you'll get intermittent
`prepared statement "__asyncpg_stmt_..." does not exist` errors under
concurrent load.

The MedMinder backend handles this via SQLAlchemy engine kwargs:

```python
# backend/src/medminder/db/__init__.py
create_async_engine(
    settings.database_url,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)
```

If you point the backend at a non-pooler Postgres (for example, a
local Docker Postgres or Supabase's *direct* connection on port
5432), you can leave these defaults — but they are also harmless.

### 1.4 Database migrations

Alembic migrations run as the Koyeb **release command**
(`alembic upgrade head`, configured in §2.1) — once per deploy, before
the new container serves traffic. `alembic.ini` deliberately omits
`sqlalchemy.url`; `alembic/env.py` reads it from
`Settings.database_url_sync` (your `DATABASE_URL`, swapped to the
sync `+psycopg` driver).

### 1.5 Security checklist

- [ ] Use the **pooler connection** (port 6543), not the direct
      connection (port 5432), to avoid exhausting connections on the
      free tier.
- [ ] Disable asyncpg prepared statements (§1.3) — the codebase does
      this, just don't override it.
- [ ] Never commit the connection string to the repository — it goes
      in environment variables only.
- [ ] **Two database roles (hardening — see §8).** Production is meant
      to run with a DDL-capable migration role and a DML-only runtime
      role. The first deploy may use the Supabase `postgres` role for
      both to get live; splitting them is the first hardening task.

---

## 2. Backend + frontend — Koyeb (one service)

### 2.1 Create the service

1. Sign up at [koyeb.com](https://koyeb.com).
2. Create a new **Web Service** connected to your GitHub repository.
3. Configure:
   - **Builder**: **Docker**.
   - **Dockerfile location**: `./Dockerfile` (the repo-root production
     Dockerfile — it builds the React app and serves it from FastAPI).
     **Build context**: the repository root.
   - **Release command**: `alembic upgrade head` — runs once per deploy
     before traffic is routed.
   - **Run command**: leave as the image default
     (`uvicorn medminder.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}`,
     no `--reload`). Koyeb injects `$PORT`.
   - **Instance type**: Eco Micro (free tier, **does not sleep**).
   - **Port**: 8000 (or let Koyeb's `$PORT` drive it).
   - **Scaling**: keep **a single instance / single worker**. The reminder
     scheduler (`REMINDERS_ENABLED=true`) runs in-process; two instances would
     each fire the dispatch tick and **double-deliver** reminders (ADR-0002).
     Do not run `uvicorn --workers N>1` or scale horizontally without
     revisiting ADR-0002.

> The dev images `backend/Dockerfile` and `frontend/Dockerfile` are for
> local docker-compose only (they run with `--reload`). Production uses
> the **root `Dockerfile`**.

### 2.2 Environment variables

Set these in the Koyeb dashboard under **Settings → Environment
variables**, per the phase table at the top of this guide.

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | From Supabase §1.2 |
| `SESSION_SECRET` | 32+ random bytes, base64 | Required in prod |
| `ENV` | `production` | |
| `TRUSTED_PROXY_COUNT` | `1` | Koyeb adds one proxy layer |
| `CORS_ORIGINS` | `https://your-app.koyeb.app` | Same-origin, so not load-bearing — set anyway |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` | from `python scripts/generate_vapid_keys.py` | Phase 7+ (private key is secret) |
| `REMINDERS_ENABLED` | `true` | Phase 7+. Starts the in-process scheduler — run a **single instance** (§2.1). |

Do **not** set `VITE_API_BASE_URL` — the frontend is built with it empty
(relative, same-origin paths) inside the image.

### 2.3 First-admin bootstrap (Phase 1b+)

The mission forbids self-registration. The first admin is created via
the Phase 1b admin CLI. After your first successful deploy:

1. In Koyeb, create a **one-shot job** on the same service image with
   the run command:
   ```
   echo "$ADMIN_PASSWORD" | medminder-admin user add \
     --email "$ADMIN_EMAIL" --name "$ADMIN_NAME" --role admin --password-stdin
   ```
   (`medminder-admin` is on `PATH` in the image — it's the project's
   console script.)
2. Set `ADMIN_EMAIL`, `ADMIN_NAME`, and `ADMIN_PASSWORD` as one-shot
   secrets on that job. Delete the job (and the secrets) after it
   succeeds.
3. Subsequent users are created in-app by the bootstrapped admin at
   `/admin/users` (ADR-0014), or by re-running this CLI job.

### 2.4 Verify

After deployment, confirm the health check:

```bash
curl https://your-app.koyeb.app/healthz
# Expected: {"status":"ok"}
```

Then open `https://your-app.koyeb.app/` in a browser — you should get the
MedMinder app (the React shell), be able to install it as a PWA, and log
in as the bootstrapped admin with the session sticking (no redirect loop).

---

## 3. Frontend

There is **no separate frontend deployment.** The React app is built by
the root `Dockerfile` (Node build stage) with `VITE_API_BASE_URL=""` and
served by FastAPI at `/`, with client-side routes falling back to
`index.html` (ADR-0017). To ship a frontend change, push to `main` and let
Koyeb rebuild — same as any backend change.

---

## 4. DNS & HTTPS

Koyeb provides automatic HTTPS on the `*.koyeb.app` subdomain. If you have
a custom domain:

1. Add it to the Koyeb service and update your DNS records as instructed.
2. Update the backend's `CORS_ORIGINS` to the custom domain (defensive;
   same-origin doesn't require it).
3. Redeploy. Because everything is one origin and `VITE_API_BASE_URL` is
   empty/relative, **no special frontend rebuild step is needed** for the
   domain change.

---

## 5. Staging — recommendation

For a free-tier hobby project, a separate full staging environment
costs more in operational overhead than it returns. The recommended
approach is:

- **Develop locally** against Docker Compose (`just dev`); merges to
  `main` auto-deploy to production.
- **No separate staging service** while the surface area is small.
- **When the project warrants it** (e.g., real users start to depend on
  it), promote a second free Supabase project + a second free Koyeb
  service on a `staging` branch.

This decision should be revisited (and likely captured as an ADR) when
the answer to "would I be embarrassed if a bad migration hit prod?"
becomes "yes."

---

## 6. Backups

Backups are taken via the Phase 1b admin CLI, which wraps `pg_dump`
and `pg_restore`. This is the supported path because:

- The CLI runs from the same code that owns the schema, so it always
  matches the current Alembic head.
- Restores can be exercised in CI against an ephemeral Postgres
  before being trusted in production.
- Supabase's free-tier UI backups exist but are not exercised by our
  test suite.

### 6.1 Manual backup

From a workstation (or a Koyeb one-shot job) with `DATABASE_URL` set:

```bash
medminder-admin db backup --out /tmp/medminder-$(date -u +%Y%m%dT%H%M%SZ).dump
```

The output file is `pg_dump --format=custom`. On Unix, the CLI
chmods it to `0600`; on Windows it prints a warning to ACL the file
manually.

**Treat backup files as protected health information.** They contain
every Argon2id password hash and every medication record.

### 6.2 Manual restore

```bash
medminder-admin db restore --in /tmp/medminder-....dump --yes
```

### 6.3 Scheduled backups

Until backup volume justifies a dedicated solution, schedule a daily
Koyeb one-shot job that runs `medminder-admin db backup` and pushes
the resulting file to encrypted object storage you control (any
S3-compatible provider with server-side encryption). Document the
target bucket and the retention policy in your operational runbook;
do not commit either to the repository.

---

## 7. Ongoing operations

### Monitoring

- **Koyeb**: Built-in logs and metrics in the dashboard (covers both the
  API and the static frontend, since it's one service).
- **Supabase**: Database health and query performance in the dashboard.

### Updating

Koyeb auto-deploys from GitHub. Push to `main` and the pipeline handles
the rest: it rebuilds the image (frontend + backend), runs the release
command `alembic upgrade head`, then routes traffic to the new container.

### Cost

All services used are within their free tiers; verify the current
limits on each provider's pricing page before relying on the numbers
below.

| Service | Free tier (verify before relying) |
|---------|------------------------------------|
| Supabase | 500 MB database, 5 GB egress/month |
| Koyeb | 1 Eco Micro instance (does not sleep) |

---

## 8. Hardening follow-ups

These are recommended once the first deploy is live and verified:

- **Two database roles (security, NON-NEGOTIABLE per the constitution).**
  Run migrations as a DDL-capable role and the app as a DML-only runtime
  role. Cleanly, this means the release command (`alembic`) uses a
  different URL than the runtime app — a small change so Alembic can read
  a separate `MIGRATION_DATABASE_URL` distinct from the runtime
  `DATABASE_URL`. Tracked as the first hardening task.
- **Scheduled, off-site, encrypted backups** (§6.3).
- **Custom domain** (§4).

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Login succeeds but immediately bounces back to `/login` | A cross-origin cookie problem. This deploy is single-origin to avoid it (ADR-0017); confirm you are **not** serving the frontend from a different host than the API, and that `ENV=production` so cookies are `Secure`. |
| `GET /` returns the API/404, not the app | The image didn't bake the frontend or `FRONTEND_DIST` isn't set. Rebuild from the root `Dockerfile`; the image sets `FRONTEND_DIST=/app/frontend_dist`. |
| Database `prepared statement "..." does not exist` | You're hitting the pooler without disabling asyncpg prepared statements. See §1.3. |
| Database connection refused | Check that you're using the pooler port (6543) and the connection string is correct (and is the `+asyncpg` form). |
| Koyeb build fails | Ensure the build uses the **root** `Dockerfile` with the repo root as context; check `backend/pyproject.toml` and `frontend/pnpm-lock.yaml` are committed. |
| `alembic upgrade head` fails on deploy | Roll back to the prior image and run the migration locally against `DATABASE_URL` to see the full traceback. |
| Bootstrap admin job fails with duplicate email | An admin already exists; use `medminder-admin user list --role admin` to confirm. |
| App refuses to start: "SESSION_SECRET must be set..." | `ENV` is non-development but `SESSION_SECRET` is unset/default. Set a strong base64 secret (§2.2). |
