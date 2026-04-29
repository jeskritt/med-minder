"""Generate the TypeScript API client from the FastAPI OpenAPI spec.

Cross-platform script (Python) — see specs/tech-stack.md §Scripts.

Usage:
    python scripts/generate_openapi_client.py

What it does:
    1. Boots the FastAPI app in-process.
    2. Dumps the OpenAPI JSON to a temp file.
    3. Shells out to ``pnpm dlx openapi-typescript`` to write the
       generated client to ``frontend/src/api/v1.d.ts``.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure the backend package is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_SRC = REPO_ROOT / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

OUTPUT_DIR = REPO_ROOT / "frontend" / "src" / "api"
OUTPUT_FILE = OUTPUT_DIR / "v1.d.ts"


def main() -> int:
    """Generate the OpenAPI TypeScript client."""
    # 1. Boot the FastAPI app and extract the OpenAPI schema
    from medminder.app import create_app  # noqa: E402

    app = create_app()
    openapi_schema = app.openapi()

    # 2. Write to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as f:
        json.dump(openapi_schema, f, indent=2)
        temp_path = f.name

    print(f"OpenAPI schema written to {temp_path}")

    # 3. Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 4. Run openapi-typescript to generate the client
    cmd = [
        "pnpm",
        "dlx",
        "openapi-typescript",
        temp_path,
        "-o",
        str(OUTPUT_FILE),
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT / "frontend"),
        check=False,
        shell=(sys.platform == "win32"),
    )

    # 5. Clean up temp file
    Path(temp_path).unlink(missing_ok=True)

    if result.returncode != 0:
        print("ERROR: openapi-typescript failed", file=sys.stderr)
        return 1

    print(f"Generated client at {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
