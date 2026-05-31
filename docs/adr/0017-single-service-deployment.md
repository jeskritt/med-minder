# ADR-0017 — Single-service deployment: FastAPI serves the API and the React SPA from one origin

## Status

**Accepted** (Deployment).

## Context

MedMinder is going to production for the first time. `docs/deployment.md`
originally described a **three-tier split**: the React build on a static host
(Vercel/Cloudflare Pages), the FastAPI backend on Koyeb, and Postgres on
Supabase — with the frontend calling the backend cross-origin via
`VITE_API_BASE_URL`.

That split is **incompatible with the app's authentication**. The session
cookie is issued with `SameSite=Lax` (`api/deps.py::set_session_cookie`) and
the API client sends it with `credentials: "include"` (`frontend/src/lib/api.ts`).
A `SameSite=Lax` cookie is **not sent on cross-site requests**, so a frontend on
`*.vercel.app` calling a backend on `*.koyeb.app` would log in successfully (the
`Set-Cookie` returns) but be treated as logged-out on every subsequent call — an
infinite redirect to `/login`. The Phase 2 auth spec assumed "same-origin in
production"; the deployment doc had drifted from that.

The realistic ways to make it work:

- **Single origin** — serve the SPA and the API from the same host.
- **`SameSite=None; Secure`** cross-site cookie — a code change that weakens the
  app's only CSRF defense (`SameSite=Lax`; explicit CSRF tokens are deferred to
  the hardening phase) and is unreliable on iOS Safari, which blocks third-party
  cookies. MedMinder is an installable PWA explicitly targeting iOS.

Two further constraints from existing decisions:

- The reminder loop is an **in-process APScheduler** that must stay alive, which
  is why the deploy targets a Koyeb Eco Micro instance that **does not sleep**
  (ADR-0002).
- The service worker performs **same-origin** `fetch(credentials: 'include')`
  for notification actions (ADR-0015); split origins would break those too.

## Decision

**Deploy as a single service: the FastAPI app serves both the API and the built
React frontend from one origin.** No change to the cookie, CORS, or any auth
logic.

- A new `Settings.frontend_dist` path. When set and the directory exists,
  `create_app` mounts the build at `/` via a `StaticFiles` subclass
  (`_SPAStaticFiles`) that **falls back to `index.html` on 404** so client-side
  deep links (`/medications`, `/reminders`, `/admin/...`) resolve on hard
  refresh. The mount is registered **last**, so the API routers and `/healthz`
  match first; only unmatched paths reach the SPA. When `frontend_dist` is unset
  (dev, tests) the mount is skipped and the API surface is unchanged.
- A new **root `Dockerfile`** (multi-stage): a Node stage builds the frontend
  with `VITE_API_BASE_URL=""` (relative, same-origin paths, baked at build
  time); the Python stage installs the backend (prod deps, no `[dev]`, no
  editable), keeps `postgresql-client-17` for the backup CLI, copies the built
  `dist`, and runs `uvicorn` (no `--reload`) on Koyeb's `$PORT`. The dev
  `backend/Dockerfile` and `frontend/Dockerfile` (which back docker-compose) are
  left untouched.
- Migrations run in the image **entrypoint** (`alembic upgrade head &&
  uvicorn ...`) on container start. Koyeb has no release/pre-deploy command
  ([feature request](https://community.koyeb.com/t/pre-deploy-jobs/1672));
  this is safe because we run a single always-on instance and the upgrade is
  idempotent. When the two-role hardening lands (DML-only runtime role),
  migrations move out of the entrypoint to a separate step.

## Consequences

### Positive
- **Zero auth code change.** `SameSite=Lax` keeps working; no CSRF regression;
  iOS PWA is unaffected. The SW's same-origin fetches keep working.
- **No CORS** in production (same origin); `CORS_ORIGINS` becomes a belt-and-
  braces setting rather than load-bearing.
- **One deploy, fewer moving parts** to operate — aligned with ADR-0002's
  single-instance, single-process model, and the simplest thing for an operator
  new to ops.

### Negative
- **No CDN for static assets** — they're served by the Python instance. At
  single-tenant scale this is immaterial; the SW precaches the shell anyway
  (ADR-0015), so repeat loads are local.
- **SPA-fallback wart**: an unmatched `/api/...` typo falls through to the mount
  and returns `index.html` (HTTP 200, HTML) instead of a JSON 404. Real
  endpoints are unaffected; acceptable for v1. A path-prefix guard could tighten
  this later.
- The frontend's API origin is **baked at image build** (`VITE_API_BASE_URL`),
  but it's empty/relative, so it never needs to change — the historical
  "rebuild to change the API URL" caveat no longer applies.

### Neutral
- If the app ever outgrows one instance, this ADR is revisited alongside
  ADR-0002 (the scheduler is the other single-instance constraint), and a
  static host / CDN split could return — but then the cookie strategy
  (`SameSite=None` + CSRF tokens, or a reverse proxy that re-unifies the origin)
  must be solved deliberately.

## Alternatives considered

- **Vercel/Cloudflare static front + Koyeb backend, unified by a reverse-proxy
  rewrite** (e.g. Vercel `rewrites` forwarding `/api`,`/auth`,`/me` to Koyeb so
  the browser still sees one origin) — viable and keeps a CDN, but adds a second
  platform and proxy config to operate. Rejected for v1 in favour of the simpler
  single service; recorded here as the natural growth path.
- **`SameSite=None; Secure` cross-site cookie** — rejected: weakens CSRF posture
  and is blocked by iOS Safari third-party-cookie restrictions, breaking the PWA
  on a primary target platform.
