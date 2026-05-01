# MedMinder

Personal medication tracker — a mobile-first Progressive Web App that
helps you take the right medication at the right time.

## Prerequisites

- **Python 3.12+**
- **Node 20+**
- **pnpm** — `npm install -g pnpm`
- **just** — [installation guide](https://github.com/casey/just#installation)
- **Docker** & **Docker Compose** — for the local dev environment
- **bash** — required by `justfile` recipes. macOS and Linux already
  have it. **Windows users need [Git Bash](https://git-scm.com/downloads)
  or [WSL](https://learn.microsoft.com/windows/wsl/install)** on
  `PATH` so `just` can find `bash`. See
  `specs/tech-stack.md` §"Scripts & cross-platform policy" for the
  rationale.

## Quickstart

```bash
# 1. Clone the repo
git clone https://github.com/your-org/med-minder.git
cd med-minder

# 2. Copy the environment file
cp .env.example .env

# 3. Start the dev environment (Postgres + backend + frontend)
just dev

# 4. Open the app
#    Frontend: http://localhost:5173
#    Backend:  http://localhost:8000
#    API docs: http://localhost:8000/docs
```

## Common commands

| Command | What it does |
|---------|-------------|
| `just dev` | Start the full dev stack (Docker Compose) |
| `just test` | Run all tests (backend + frontend) |
| `just lint` | Run all linters (ruff, eslint, prettier) |
| `just typecheck` | Run type checkers (mypy, tsc) |
| `just generate-client` | Regenerate the TypeScript API client from OpenAPI |
| `just migrate` | Run database migrations *(Phase 1+)* |

## Project structure

```
med-minder/
├── backend/         # FastAPI service + admin CLI
├── frontend/        # React + Vite PWA
├── scripts/         # Dev/CI helper scripts (Python only)
├── specs/           # Constitution: mission, tech stack, roadmap
├── docs/            # User stories, ADRs, diagrams, deployment guide
├── docker-compose.yml
└── justfile
```

## Documentation

- [Mission & Vision](specs/mission.md)
- [Roadmap](specs/roadmap.md)
- [Tech Stack](specs/tech-stack.md)
- [User Stories & Use Cases](docs/user_stories.md)
- [Glossary](docs/glossary.md)
- [Architecture Decision Records](docs/adr/)
- [Design Notes](docs/design/)
- [Deployment Guide](docs/deployment.md)
- [Security Policy](SECURITY.md)

## License

See [LICENSE](LICENSE).
