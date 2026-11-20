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
FROM node:24-slim AS frontend-build

WORKDIR /frontend

# Pin pnpm to the version that produced frontend/pnpm-lock.yaml.
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
FROM python:3.14-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONTZPATH="" \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    FRONTEND_DIST=/app/frontend_dist \
    RUN_MIGRATIONS_ON_STARTUP=true

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
    && apt-get install -y --no-install-recommends postgresql-client-17 tzdata \
    && apt-get purge -y curl gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Install the backend (locked production deps only — no editable, no [dev] extras).
# Copy metadata + lockfile + src first so the venv layer caches when only alembic/ changes.
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src/ ./src/
RUN uv sync --frozen --no-dev --no-editable

# Migrations run on startup (unless RUN_MIGRATIONS_ON_STARTUP=false);
# alembic.ini and the migration scripts are not part of the installed package.
COPY backend/alembic/ ./alembic/
COPY backend/alembic.ini ./alembic.ini

# The built SPA, served at / by FastAPI when FRONTEND_DIST points at it.
COPY --from=frontend-build /frontend/dist ./frontend_dist

# Drop root privileges for the runtime process.
# Use GID/UID 1000 so Render Secret Files (/etc/secrets/*) are readable by appuser.
RUN addgroup --gid 1000 app \
    && adduser --uid 1000 --ingroup app --disabled-password --gecos "" --no-create-home appuser \
    && chown -R appuser:app /app

USER appuser

EXPOSE 8000

# Run migrations on startup by default, then launch uvicorn.
#
# - Default (RUN_MIGRATIONS_ON_STARTUP=true): runs `alembic upgrade head` first
#   (using MIGRATION_DATABASE_URL if set, else DATABASE_URL); `set -e` aborts
#   boot if the migration fails. Safe for a single always-on instance (ADR-0002).
# - Hardened two-role mode (RUN_MIGRATIONS_ON_STARTUP=false): skips startup
#   migrations so the runtime container only holds DML-only DATABASE_URL and
#   never receives DDL credentials; run migrations out-of-band before deploy
#   (see docs/deployment.md §7 & §8).
CMD ["sh", "-c", "set -e; if [ \"${RUN_MIGRATIONS_ON_STARTUP:-true}\" != \"false\" ]; then alembic upgrade head; fi; exec uvicorn medminder.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
