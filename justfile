# MedMinder — justfile
# Common dev commands. Run `just --list` to see all targets.
#
# Requires: just (https://github.com/casey/just)

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# ---------------------------------------------------------------------------
# Dev environment
# ---------------------------------------------------------------------------

# Bring up the full dev stack (Postgres + backend + frontend)
dev:
    docker compose up --build

# Tear down the dev stack
dev-down:
    docker compose down

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

# Run all tests (backend + frontend)
test: test-backend test-frontend

# Run backend tests (pytest)
test-backend:
    cd backend; python -m pytest tests/ -v

# Run frontend tests (vitest)
test-frontend:
    pnpm --prefix frontend run test

# ---------------------------------------------------------------------------
# Linting
# ---------------------------------------------------------------------------

# Run all linters
lint: lint-backend lint-frontend

# Lint backend (ruff)
lint-backend:
    python -m ruff check backend/src/ backend/tests/

# Lint frontend (eslint + prettier)
lint-frontend:
    pnpm --prefix frontend run lint
    pnpm --prefix frontend run format:check

# ---------------------------------------------------------------------------
# Type checking
# ---------------------------------------------------------------------------

# Run all type checkers
typecheck: typecheck-backend typecheck-frontend

# Type-check backend (mypy --strict)
typecheck-backend:
    python -m mypy --strict backend/src/

# Type-check frontend (tsc --noEmit)
typecheck-frontend:
    pnpm --prefix frontend run typecheck

# ---------------------------------------------------------------------------
# Database migrations (Phase 1+)
# ---------------------------------------------------------------------------

# Run database migrations
migrate:
    python -m alembic -c backend/alembic.ini upgrade head

# Create a new migration revision
migrate-rev message:
    python -m alembic -c backend/alembic.ini revision --autogenerate -m "{{message}}"

# Roll back the most recent migration
migrate-down:
    python -m alembic -c backend/alembic.ini downgrade -1

# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

# Generate the TypeScript API client from the FastAPI OpenAPI spec
generate-client:
    python scripts/generate_openapi_client.py
