# MedMinder — justfile
# Common dev commands. Run `just --list` to see all targets.
#
# Requires: just (https://github.com/casey/just)
# On Windows, recipes use bash via Git Bash or WSL.

set shell := ["bash", "-cu"]

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
    cd backend && python -m pytest tests/ -v

# Run frontend tests (vitest)
test-frontend:
    cd frontend && pnpm test

# ---------------------------------------------------------------------------
# Linting
# ---------------------------------------------------------------------------

# Run all linters
lint: lint-backend lint-frontend

# Lint backend (ruff)
lint-backend:
    cd backend && python -m ruff check src/ tests/

# Lint frontend (eslint + prettier)
lint-frontend:
    cd frontend && pnpm lint && pnpm format:check

# ---------------------------------------------------------------------------
# Type checking
# ---------------------------------------------------------------------------

# Run all type checkers
typecheck: typecheck-backend typecheck-frontend

# Type-check backend (mypy --strict)
typecheck-backend:
    cd backend && python -m mypy --strict src/

# Type-check frontend (tsc --noEmit)
typecheck-frontend:
    cd frontend && pnpm typecheck

# ---------------------------------------------------------------------------
# Database migrations (Phase 1+)
# ---------------------------------------------------------------------------

# Run database migrations
migrate:
    cd backend && python -m alembic upgrade head

# Create a new migration revision
migrate-rev message:
    cd backend && python -m alembic revision --autogenerate -m "{{message}}"

# Roll back the most recent migration
migrate-down:
    cd backend && python -m alembic downgrade -1

# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

# Generate the TypeScript API client from the FastAPI OpenAPI spec
generate-client:
    python scripts/generate_openapi_client.py
