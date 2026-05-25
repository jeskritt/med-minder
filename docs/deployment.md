# MedMinder — Deployment Guide

A beginner-friendly guide to deploying MedMinder using free-tier
infrastructure. This setup keeps background timers (APScheduler) alive
and avoids container-sleep limitations.

## Architecture overview

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│                  │     │                  │     │                  │
│  Vercel /        │────▶│  Koyeb           │────▶│  Supabase        │
│  Cloudflare      │     │  (Backend)       │     │  (PostgreSQL)    │
│  (Frontend)      │     │                  │     │                  │
│                  │     │                  │     │                  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
   Static hosting           Eco Micro instance      Free-tier Postgres
   (no sleep)               (no sleep)               Direct connection
```

- **Frontend → Vercel or Cloudflare Pages**: Serves the static React
  build. Both platforms offer generous free tiers with global CDN and
  zero cold starts.
- **Backend → Koyeb Free Tier**: Runs the FastAPI service on an Eco
  Micro instance that **does not sleep**, keeping APScheduler alive for
  reliable reminder delivery.
- **Database → Supabase Free Tier**: Provides a managed PostgreSQL
  instance. We connect directly via `asyncpg` (standard PostgreSQL
  protocol), **not** through the Supabase REST or GraphQL APIs.

## What lives where, by phase

The deployment doesn't change shape between phases, but the set of
required environment variables and migrations grows:

| Variable / step | Required from phase | Notes |
|-----------------|---------------------|-------|
| `DATABASE_URL` | Phase 1 | Supabase connection string. |
| `alembic upgrade head` on backend boot | Phase 1 | Release command on Koyeb. |
| `medminder-admin user add` (bootstrap admin) | Phase 1b | One-shot Koyeb job after first deploy. |
| `medminder-admin db backup` (scheduled) | Phase 1b | One-shot or cron job — see §6. |
| `SESSION_SECRET` | Phase 2 | 32+ random bytes, base64. Used to sign session cookies. |
| `CORS_ORIGINS` | Phase 2 | Frontend production URL(s). |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | Phase 7 | Web Push keys; generate with `python scripts/generate_vapid_keys.py`. **Private key is a secret** — env-only, never logged or returned. |
| `REMINDERS_ENABLED` | Phase 7 | `true` in production (starts the in-process reminder scheduler). **Single instance only** — see §2.1. |
| `ENV=production` | Always | Disables permissive dev CORS and dev-only diagnostics. |

When you complete a phase, remove the "from phase X" comment for the
variables it introduces, since they become baseline.

---

## Prerequisites

- A [GitHub](https://github.com) account (all three services support
  GitHub-based deployment).
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
3. Convert it to the SQLAlchemy `+asyncpg` form:
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
# backend/src/medminder/db/__init__.py (Phase 1)
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

Alembic migrations run on backend boot via `alembic upgrade head`. On
Koyeb, this is the **release command** (configured in §2.1) — it runs
once per deploy before the new container starts serving traffic.

### 1.5 Security checklist

- [ ] Use the **pooler connection** (port 6543), not the direct
      connection (port 5432), to avoid exhausting connections on the
      free tier.
- [ ] Disable asyncpg prepared statements (§1.3) — the codebase does
      this, just don't override it.
- [ ] Never commit the connection string to the repository — it goes
      in environment variables only.
- [ ] Create a **dedicated runtime database role** with
      `SELECT, INSERT, UPDATE, DELETE` only. The default
      `postgres` superuser runs migrations; the runtime role does
      not. Phase 1 documents the SQL to create the runtime role.

---

## 2. Backend — Koyeb

### 2.1 Create the service

1. Sign up at [koyeb.com](https://koyeb.com).
2. Create a new **Web Service** connected to your GitHub repository.
3. Configure:
   - **Build command**: `cd backend && pip install .`
   - **Release command** *(Phase 1+)*: `cd backend && alembic upgrade head`
   - **Run command**: `cd backend && uvicorn medminder.app:create_app --factory --host 0.0.0.0 --port 8000`
   - **Instance type**: Eco Micro (free tier, **does not sleep**)
   - **Port**: 8000
   - **Scaling**: keep **a single instance / single worker**. The reminder
     scheduler (`REMINDERS_ENABLED=true`) runs in-process; two instances would
     each fire the dispatch tick and **double-deliver** reminders (ADR-0002).
     Do not run `uvicorn --workers N>1` or scale horizontally without
     revisiting ADR-0002.

### 2.2 Environment variables

Set these in the Koyeb dashboard under **Settings → Environment
variables**, per the phase table at the top of this guide.

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | From Supabase §1.2 |
| `CORS_ORIGINS` | `https://your-frontend.vercel.app` | Phase 2+ |
| `SESSION_SECRET` | 32+ random bytes, base64 | Phase 2+ |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` | from `python scripts/generate_vapid_keys.py` | Phase 7+ (private key is secret) |
| `REMINDERS_ENABLED` | `true` | Phase 7+. Starts the in-process scheduler — run a **single instance** (§2.1). |
| `ENV` | `production` | |

### 2.3 First-admin bootstrap (Phase 1b+)

The mission forbids self-registration. The first admin is created via
the Phase 1b admin CLI. After your first successful deploy:

1. In Koyeb, create a **one-shot job** on the same service image with
   the run command:
   ```
   cd backend && echo "$ADMIN_PASSWORD" | python -m medminder.cli user add \
     --email "$ADMIN_EMAIL" --name "$ADMIN_NAME" --role admin --password-stdin
   ```
2. Set `ADMIN_EMAIL`, `ADMIN_NAME`, and `ADMIN_PASSWORD` as one-shot
   secrets on that job. Delete the job (and the secrets) after it
   succeeds.
3. Subsequent users are created by the bootstrapped admin from the
   same image (re-run the job with different env vars, or run locally
   against the production `DATABASE_URL`).

### 2.4 Verify

After deployment, confirm the health check:

```bash
curl https://your-app.koyeb.app/healthz
# Expected: {"status":"ok"}
```

---

## 3. Frontend — Vercel (recommended) or Cloudflare Pages

### Important: `VITE_API_BASE_URL` is build-time

Vite inlines `import.meta.env.VITE_*` variables at build time. If you
change the backend domain, **you must trigger a rebuild** of the
frontend — restarting the deployment without a rebuild will keep the
old URL.

### Option A: Vercel

1. Sign up at [vercel.com](https://vercel.com) and import your GitHub
   repository.
2. Configure:
   - **Framework preset**: Vite
   - **Root directory**: `frontend`
   - **Build command**: `pnpm build`
   - **Output directory**: `dist`
3. Add an environment variable:
   - `VITE_API_BASE_URL` = `https://your-app.koyeb.app`
4. Deploy. Vercel will auto-deploy on every push to `main`.

### Option B: Cloudflare Pages

1. Sign up at [dash.cloudflare.com](https://dash.cloudflare.com) and
   create a new **Pages** project connected to your GitHub repo.
2. Configure:
   - **Build command**: `cd frontend && pnpm install && pnpm build`
   - **Build output directory**: `frontend/dist`
3. Add the same `VITE_API_BASE_URL` environment variable.
4. Deploy.

### Verify

Visit your frontend URL. You should see "Hello MedMinder" with a green
health status indicator fetched from the backend.

---

## 4. DNS & HTTPS

Both Vercel and Cloudflare provide automatic HTTPS. If you have a custom
domain:

1. Add it in the hosting dashboard.
2. Update your DNS records as instructed.
3. Update the backend's `CORS_ORIGINS` to include the custom domain.
4. **Rebuild the frontend** so the new origin is baked in (see §3
   note above).

---

## 5. Staging — recommendation

For a free-tier hobby project, a separate full staging environment
costs more in operational overhead than it returns. The recommended
approach is:

- **Preview deployments on the frontend** — Vercel and Cloudflare
  Pages both deploy every PR to a unique URL automatically. No
  setup needed.
- **No separate staging backend** while the surface area is small.
  Develop locally against Docker Compose; merges to `main`
  auto-deploy to production.
- **When the project warrants it** (e.g., real users start to depend
  on it), promote one of the following:
  - A second free Supabase project + a second free Koyeb service on
    a `staging` branch, with `CORS_ORIGINS` matching the
    Vercel/Cloudflare preview URL pattern.
  - Or a single Koyeb staging service that points at a separate
    Supabase staging project; promote builds from `staging` to a
    production Koyeb service using image tags.

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

- **Koyeb**: Built-in logs and metrics in the dashboard.
- **Supabase**: Database health and query performance in the dashboard.
- **Vercel/Cloudflare**: Deployment logs and analytics.

### Updating

All three services support auto-deploy from GitHub. Push to `main` and
the pipeline handles the rest. The backend's release command runs
`alembic upgrade head` before traffic is routed to the new container.

### Cost

All services used are within their free tiers; verify the current
limits on each provider's pricing page before relying on the numbers
below.

| Service | Free tier (verify before relying) |
|---------|------------------------------------|
| Supabase | 500 MB database, 5 GB egress/month |
| Koyeb | 1 Eco Micro instance (does not sleep) |
| Vercel | 100 GB bandwidth/month |
| Cloudflare Pages | Unlimited bandwidth |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Backend returns CORS error | Verify `CORS_ORIGINS` includes your exact frontend URL (with `https://`) |
| Database `prepared statement "..." does not exist` | You're hitting the pooler without disabling asyncpg prepared statements. See §1.3. |
| Database connection refused | Check that you're using the pooler port (6543) and the connection string is correct |
| Frontend shows "error" for health check | Verify `VITE_API_BASE_URL` is set; remember it is build-time, so changing it requires a rebuild |
| Koyeb build fails | Ensure `backend/pyproject.toml` is valid and all deps are pinned |
| `alembic upgrade head` fails on deploy | Roll back to the prior image and run the migration locally against `DATABASE_URL` to see the full traceback |
| Bootstrap admin job fails with duplicate email | An admin already exists; use `medminder-admin user list --role admin` to confirm |
