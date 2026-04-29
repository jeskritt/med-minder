# MedMinder — Scripts

Dev and CI helper scripts. All scripts in this directory are **Python**
to ensure cross-platform compatibility (Windows dev, Linux deploy).

## Cross-platform scripting policy

- **Default to Python** for any non-trivial script. Python is already a
  project dependency and runs identically on Windows and Linux.
- **Bash is allowed only inside Linux containers** (Dockerfile `RUN`
  steps, GitHub Actions Linux jobs). It must not be a developer's
  expected entry point.
- **`justfile` recipes** stay short and shell out to Python scripts for
  anything beyond a one-liner.

## Scripts

| Script | Purpose |
|--------|---------|
| `generate_openapi_client.py` | Generates the TypeScript API client from the FastAPI OpenAPI spec |
