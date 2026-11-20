FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /uvx /usr/local/bin/

ENV PYTHONTZPATH="" \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# postgresql-client-17 provides pg_dump / pg_restore for the
# `medminder-admin db backup|restore` CLI (and its tests). The client
# major must match (or exceed) the Postgres 17 server, so pull it from
# the PGDG apt repo rather than Debian's older default.
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

# Copy project metadata, lockfile, and source together so the editable
# install can find the package and Docker caches the venv layer when only
# test/config files change.
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install the locked package (editable) with dev extras
RUN uv sync --frozen --extra dev

# Copy everything else (tests, alembic, etc.)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "medminder.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]
