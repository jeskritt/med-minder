"""Argon2id round-trip tests."""

from __future__ import annotations

from medminder.domain.passwords import (
    MIN_PASSWORD_LENGTH,
    hash_password,
    password_too_short,
    verify_password,
)


def test_round_trip() -> None:
    h = hash_password("correct horse battery staple")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "correct horse battery staple") is True


def test_mismatch_returns_false() -> None:
    h = hash_password("correct horse battery staple")
    assert verify_password(h, "wrong password value") is False


def test_unique_hashes() -> None:
    """Argon2id includes a random salt — same input → distinct hashes."""
    a = hash_password("twelve chars!!")
    b = hash_password("twelve chars!!")
    assert a != b


def test_password_too_short_boundary() -> None:
    assert MIN_PASSWORD_LENGTH == 12
    assert password_too_short("a" * 11) is True
    assert password_too_short("a" * 12) is False


def test_corrupt_hash_returns_false() -> None:
    assert verify_password("not-a-valid-hash", "anything") is False
