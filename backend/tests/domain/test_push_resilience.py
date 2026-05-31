"""Push delivery resilience tests (Phase 7, T050, FR-016)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pywebpush import WebPushException

from medminder.domain import push as push_mod
from medminder.domain.crypto import build_fernet, encrypt_secret
from medminder.domain.push import PushResult, send_web_push
from medminder.settings import Settings

# Keys are stored encrypted at rest (ADR-0020); the sender decrypts them.
_FERNET = build_fernet(Settings(env="development"))


class _Sub:
    endpoint = "https://push.example/x"
    p256dh = encrypt_secret(_FERNET, "pubkey")
    auth = encrypt_secret(_FERNET, "authsecret")


def _settings(max_attempts: int = 3) -> Settings:
    return Settings(
        env="development",
        vapid_private_key="PRIVATEKEY",
        vapid_public_key="PUB",
        vapid_subject="mailto:a@b.test",
        reminder_send_max_attempts=max_attempts,
    )


async def test_transient_error_retries_then_gives_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def fake_webpush(**_kwargs: Any) -> None:
        calls["n"] += 1
        raise WebPushException("boom", response=SimpleNamespace(status_code=500))

    monkeypatch.setattr(push_mod, "webpush", fake_webpush)
    result = await send_web_push(
        subscription=_Sub(), payload={}, settings=_settings(max_attempts=3)
    )
    assert result == PushResult(delivered=False, gone=False)
    assert calls["n"] == 3  # retried up to the configured maximum


async def test_gone_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_webpush(**_kwargs: Any) -> None:
        calls["n"] += 1
        raise WebPushException("gone", response=SimpleNamespace(status_code=410))

    monkeypatch.setattr(push_mod, "webpush", fake_webpush)
    result = await send_web_push(
        subscription=_Sub(), payload={}, settings=_settings(max_attempts=3)
    )
    assert result == PushResult(delivered=False, gone=True)
    assert calls["n"] == 1  # permanent failure → no retry


async def test_succeeds_on_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_webpush(**_kwargs: Any) -> None:
        calls["n"] += 1
        if calls["n"] < 2:
            raise WebPushException(
                "boom", response=SimpleNamespace(status_code=500)
            )

    monkeypatch.setattr(push_mod, "webpush", fake_webpush)
    result = await send_web_push(
        subscription=_Sub(), payload={}, settings=_settings(max_attempts=3)
    )
    assert result == PushResult(delivered=True, gone=False)
    assert calls["n"] == 2  # recovered on the second attempt
