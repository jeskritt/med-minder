"""Argon2id password hashing.

This module is the single source of truth for password hashing
parameters — the CLI calls these helpers, and the future Phase 2 auth
middleware will reuse them verbatim.

The hash + verify functions never log raw passwords or hashes.
Callers are expected to do the same.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# argon2-cffi defaults are mission-conformant — see ADR/Phase 1
# requirements.  Centralizing them here means Phase 2 auth doesn't
# accidentally drift from CLI-issued hashes.
_HASHER: PasswordHasher = PasswordHasher()

MIN_PASSWORD_LENGTH: int = 12


def hash_password(plain: str) -> str:
    """Hash ``plain`` with Argon2id; return the encoded hash string."""
    return _HASHER.hash(plain)


def verify_password(stored_hash: str, plain: str) -> bool:
    """Constant-time verify.  Returns ``False`` on mismatch — never raises."""
    try:
        return _HASHER.verify(stored_hash, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        # An unrelated argon2 error (corrupt hash, unsupported variant)
        # is treated as a verification failure — the alternative is to
        # leak failure modes to attackers.
        return False


def password_too_short(plain: str) -> bool:
    return len(plain) < MIN_PASSWORD_LENGTH
