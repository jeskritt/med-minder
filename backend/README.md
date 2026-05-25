# MedMinder — Backend

FastAPI service powering the MedMinder API, plus a Typer-based admin CLI
for user management.

## Stack

- **Language / runtime:** Python 3.12+
- **Framework:** FastAPI + Pydantic v2 (strict mode)
- **ORM / migrations:** SQLAlchemy 2.0 + Alembic
- **Auth:** Server-side sessions with signed HTTP-only cookies (Phase 2+)
- **Testing:** pytest + pytest-asyncio + pytest-cov + httpx (real Postgres)
- **Lint / type:** ruff + mypy `--strict`

## Running locally

The backend is designed to run via Docker Compose (see top-level README).
For direct execution during development:

```bash
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn medminder.app:create_app --factory --reload --port 8000
```

## Database migrations

```bash
just migrate                    # alembic upgrade head
just migrate-rev "message"      # generate a new autogen revision
just migrate-down               # alembic downgrade -1
```

Tests run against the same Postgres pointed to by `DATABASE_URL` and
expect `alembic upgrade head` to be applied (the test session-scoped
fixture runs it once automatically).

## Admin CLI

The `medminder-admin` console script is installed by
`pyproject.toml` (`[project.scripts]`).  Once you've installed the
package, both invocations are equivalent:

```bash
medminder-admin --help
python -m medminder.cli --help
```

### User management

```bash
echo 'correct horse battery staple' | medminder-admin user add \
    --email admin@example.com --name "Admin" --role admin --password-stdin

medminder-admin user list
medminder-admin user list --role admin --include-deleted

echo 'new password value here' | medminder-admin user update \
    --email admin@example.com --password-stdin --name "Renamed"

# Quiet hours are admin-managed (like timezone): set both bounds together,
# or clear them. Reminders due inside the window defer to its end (UC-5.3).
medminder-admin user update --email admin@example.com \
    --quiet-hours-start 22:00 --quiet-hours-end 07:00
medminder-admin user update --email admin@example.com --clear-quiet-hours

medminder-admin user delete --email admin@example.com   # soft delete
```

There is no `--password` flag by design — passwords are always read
from stdin to keep them out of process listings and shell history.
The minimum length is 12 characters; shorter inputs are rejected.

### Database backup / restore

```bash
medminder-admin db backup  --out /tmp/medminder.dump
medminder-admin db restore --in  /tmp/medminder.dump --yes
```

`db backup` shells out to `pg_dump --format=custom`; `db restore`
shells out to `pg_restore --clean --if-exists`.  Connection details
flow via libpq env vars derived from `DATABASE_URL` so credentials
never appear on the command line.

On Unix the backup file is `chmod 0600` after writing.  On Windows
the CLI prints an ACL-warning reminder; restrict the file manually
with `icacls`.

**Backup files contain every Argon2id password hash and every
medication record — treat them as protected health information.**

## Argon2id parameters

Hashing parameters live as module-level constants in
`medminder.domain.passwords`.  Both the CLI and the future Phase 2
HTTP auth code reuse the same `PasswordHasher` instance and
`MIN_PASSWORD_LENGTH = 12`.  Drift between them is impossible by
construction.

## Database roles (production)

Two distinct database roles are used in production:

- **Migration runner** — privileged role used by `alembic upgrade head`
  on each deploy.  Has DDL rights.
- **Runtime app** — least-privilege role used by the FastAPI app and
  the admin CLI day-to-day.  Granted `SELECT, INSERT, UPDATE, DELETE`
  on tables only; no DDL.

`docs/deployment.md` documents the Supabase setup and which role is
used where.

## Windows: Postgres client tools

The `db backup` / `db restore` CLI commands and their tests require
`pg_dump` and `pg_restore` on `PATH`.

- **Linux / macOS:** `apt-get install postgresql-client` (or your
  distro's equivalent) / `brew install libpq`.
- **Windows:** the standard installer at
  https://www.postgresql.org/download/windows/ ships
  `pg_dump.exe` and `pg_restore.exe` under
  `C:\Program Files\PostgreSQL\<version>\bin`.  Either add that
  directory to `PATH` or check the *Command Line Tools* component
  during install.  Verify with `pg_dump --version`.

## Session cookie configuration (Phase 2+)

Auth uses a signed, HTTP-only session cookie minted by ``POST
/auth/login``.  The signing key is read from ``SESSION_SECRET``.

- **Development** (`ENV=development`): a fixed insecure fallback is used
  if ``SESSION_SECRET`` is unset, so a fresh checkout boots without
  extra config.  The cookie is set with ``Secure=False`` so it works
  over the Vite dev server's plain-HTTP origin.
- **Any other environment**: ``SESSION_SECRET`` **must** be set
  explicitly to a strong random value (e.g. ``openssl rand -hex 32``).
  The app refuses to start otherwise.  ``Secure=True`` is enforced.

Cookie name is controlled by ``SESSION_COOKIE_NAME`` (default
``mm_session``).  See ``docs/diagrams/login-sequence.md`` for the
end-to-end login flow.

## CORS policy

- **Development:** CORS is permissive for the local Vite dev server origin
  (`http://localhost:5173`). This is set via the `CORS_ORIGINS` env var.
- **Production:** `CORS_ORIGINS` defaults to an empty list (deny-all). You
  must explicitly set it to your frontend's production origin.
