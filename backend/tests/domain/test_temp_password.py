"""Unit tests for ``generate_temp_password`` (FR-004)."""

from __future__ import annotations

from medminder.domain.passwords import (
    MIN_PASSWORD_LENGTH,
    generate_temp_password,
    hash_password,
    password_too_short,
    verify_password,
)


def test_generated_password_clears_minimum_length() -> None:
    pw = generate_temp_password()
    assert len(pw) >= MIN_PASSWORD_LENGTH
    assert not password_too_short(pw)


def test_generated_passwords_are_unique() -> None:
    # A CSPRNG should not repeat across a small sample.
    sample = {generate_temp_password() for _ in range(100)}
    assert len(sample) == 100


def test_generated_password_hashes_and_verifies() -> None:
    pw = generate_temp_password()
    stored = hash_password(pw)
    assert stored != pw  # the hash is not the plaintext
    assert verify_password(stored, pw)
