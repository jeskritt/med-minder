# Production image: a single service that serves BOTH the FastAPI API and
# the built React frontend from one origin (ADR-0017).  Serving them
# together keeps the `SameSite=Lax` session cookie working without CORS,
# and runs on one no-sleep Koyeb instance so the in-process APScheduler
# reminder loop (ADR-0002) stays alive.
#
# Build context is the REPOSITORY ROOT:
#   docker build -t medminder:prod .
#
# The dev images (backend/Dockerfile, frontend/Dockerfile) are unrelated;
# they back docker-compose for local development and run with --reload.

# ---------------------------------------------------------------------------
# Stage 1 — build the static frontend.
# VITE_API_BASE_URL is empty so the client calls relative, same-origin paths
# (see frontend/src/lib/api.ts); the value is baked in at build time.
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend-build

WORKDIR /frontend

# Pin pnpm to the version that produced frontend/pnpm-lock.yaml. `@latest`
# is a moving target and recent majors require a newer Node than node:20.
RUN corepack enable && corepack prepare pnpm@10.33.2 --activate

# Install deps first (cached unless the manifest/lockfile change).
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./

ENV VITE_API_BASE_URL=""
RUN pnpm build

# ---------------------------------------------------------------------------
# Stage 2 — Python runtime serving the API + the built shell.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIST=/app/frontend_dist

WORKDIR /app

# postgresql-client-17 provides pg_dump / pg_restore for the
# `medminder-admin db backup|restore` CLI (used by scheduled backup jobs).
# The client major must match (or exceed) the Postgres 17 server, so pull it
# from the PGDG apt repo rather than Debian's older default.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-17 \
    && apt-get purge -y curl gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Install the backend (production deps only — no editable, no [dev] extras).
# Copy metadata + src first so the pip layer caches when only alembic/ changes.
COPY backend/pyproject.toml ./
COPY backend/src/ ./src/
RUN pip install .

# Migrations run as the release command (`alembic upgrade head`); alembic.ini
# and the migration scripts are not part of the installed package.
COPY backend/alembic/ ./alembic/
COPY backend/alembic.ini ./alembic.ini

# The built SPA, served at / by FastAPI when FRONTEND_DIST points at it.
COPY --from=frontend-build /frontend/dist ./frontend_dist

EXPOSE 8000

# Run migrations on startup, then launch the app. Koyeb has no native
# release/pre-deploy command (community.koyeb.com/t/pre-deploy-jobs/1672),
# so the entrypoint runs `alembic upgrade head` first; `&&` aborts the boot
# if it fails. This is safe because we run a SINGLE always-on instance
# (ADR-0002) and the upgrade is idempotent. exec-form sh -c so ${PORT}
# (injected by Koyeb) expands and `exec` hands PID 1 to uvicorn for clean
# SIGTERM shutdown; falls back to 8000.
#
# NOTE: this couples migrations to the app's DB role (needs DDL). When the
# two-role hardening lands (DML-only runtime role; see docs/deployment.md
# §8), migrations move out of this entrypoint to a separate step.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn medminder.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
