# MedMinder — Backend

FastAPI service powering the MedMinder API, plus a Typer-based admin CLI
for user management.

## Stack

- **Language / runtime:** Python 3.12+
- **Framework:** FastAPI + Pydantic v2 (strict mode)
- **ORM / migrations:** SQLAlchemy 2.0 + Alembic (Phase 1+)
- **Auth:** Server-side sessions with signed HTTP-only cookies (Phase 3+)
- **Testing:** pytest + pytest-asyncio + httpx
- **Lint / type:** ruff + mypy `--strict`

## Running locally

The backend is designed to run via Docker Compose (see top-level README).
For direct execution during development:

```bash
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn medminder.app:create_app --factory --reload --port 8000
```

## CORS policy

- **Development:** CORS is permissive for the local Vite dev server origin
  (`http://localhost:5173`). This is set via the `CORS_ORIGINS` env var.
- **Production:** `CORS_ORIGINS` defaults to an empty list (deny-all). You
  must explicitly set it to your frontend's production origin.
