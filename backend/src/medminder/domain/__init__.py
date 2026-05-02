"""Domain layer.

Pure-Python orchestration that the CLI (Phase 1b) and the future HTTP
auth code (Phase 2) both call into.  No FastAPI, no Typer imports here
— just SQLAlchemy and ``argon2_cffi``.
"""
