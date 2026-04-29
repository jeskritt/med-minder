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
2. Under **Connection string → URI**, copy the string. It looks like:
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```
3. Use the **Transaction (port 6543)** pooler mode for web applications.

### 1.3 Security checklist

- [ ] Use the **pooler connection** (port 6543), not the direct
      connection (port 5432), to avoid exhausting connections on the
      free tier.
- [ ] Never commit the connection string to the repository — it goes
      in environment variables only.
- [ ] Consider creating a dedicated database user with limited
      privileges instead of using the default `postgres` superuser.

---

## 2. Backend — Koyeb

### 2.1 Create the service

1. Sign up at [koyeb.com](https://koyeb.com).
2. Create a new **Web Service** connected to your GitHub repository.
3. Configure:
   - **Build command**: `cd backend && pip install .`
   - **Run command**: `uvicorn medminder.app:create_app --factory --host 0.0.0.0 --port 8000`
   - **Instance type**: Eco Micro (free tier, **does not sleep**)
   - **Port**: 8000

### 2.2 Environment variables

Set these in the Koyeb dashboard under **Settings → Environment
variables**:

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | From Supabase §1.2 |
| `CORS_ORIGINS` | `https://your-frontend.vercel.app` | Your frontend URL |
| `ENV` | `production` | |

### 2.3 Verify

After deployment, confirm the health check:

```bash
curl https://your-app.koyeb.app/healthz
# Expected: {"status":"ok"}
```

---

## 3. Frontend — Vercel (recommended) or Cloudflare Pages

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

---

## 5. Ongoing operations

### Monitoring

- **Koyeb**: Built-in logs and metrics in the dashboard.
- **Supabase**: Database health and query performance in the dashboard.
- **Vercel/Cloudflare**: Deployment logs and analytics.

### Updating

All three services support auto-deploy from GitHub. Push to `main` and
the pipeline handles the rest.

### Cost

All services used are within their free tiers:

| Service | Free tier limits |
|---------|-----------------|
| Supabase | 500 MB database, 1 GB transfer/month |
| Koyeb | 1 Eco Micro instance (does not sleep) |
| Vercel | 100 GB bandwidth/month |
| Cloudflare Pages | Unlimited bandwidth |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Backend returns CORS error | Verify `CORS_ORIGINS` includes your exact frontend URL (with `https://`) |
| Database connection refused | Check that you're using the pooler port (6543) and the connection string is correct |
| Frontend shows "error" for health check | Verify `VITE_API_BASE_URL` is set and the backend is deployed |
| Koyeb build fails | Ensure `backend/pyproject.toml` is valid and all deps are pinned |
