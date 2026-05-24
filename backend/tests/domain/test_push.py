"""Web Push sender tests (Phase 7, T011) — pywebpush mocked, no network."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pywebpush import WebPushException

from medminder.domain import push as push_mod
from medminder.domain.push import PushResult, send_web_push
from medminder.settings import Settings


class _Sub:
    """Duck-typed stand-in for a PushSubscription row."""

    endpoint = "https://push.example/x"
    p256dh = "pubkey"
    auth = "authsecret"


def _settings() -> Settings:
    return Settings(
        env="development",
        vapid_private_key="PRIVATEKEYVALUE",
        vapid_public_key="PUB",
        vapid_subject="mailto:a@b.test",
    )


async def test_skipped_when_no_vapid_key() -> None:
    result = await send_web_push(
        subscription=_Sub(), payload={"x": 1}, settings=Settings(env="development")
    )
    assert result == PushResult(delivered=False, gone=False)


async def test_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_webpush(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(push_mod, "webpush", fake_webpush)
    result = await send_web_push(
        subscription=_Sub(), payload={"title": "hi"}, settings=_settings()
    )
    assert result == PushResult(delivered=True, gone=False)
    assert captured["vapid_private_key"] == "PRIVATEKEYVALUE"


async def test_gone_on_410(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_webpush(**_kwargs: Any) -> None:
        raise WebPushException("gone", response=SimpleNamespace(status_code=410))

    monkeypatch.setattr(push_mod, "webpush", fake_webpush)
    result = await send_web_push(
        subscription=_Sub(), payload={}, settings=_settings()
    )
    assert result == PushResult(delivered=False, gone=True)


async def test_transient_error_not_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_webpush(**_kwargs: Any) -> None:
        raise WebPushException("boom", response=SimpleNamespace(status_code=500))

    monkeypatch.setattr(push_mod, "webpush", fake_webpush)
    result = await send_web_push(
        subscription=_Sub(), payload={}, settings=_settings()
    )
    assert result == PushResult(delivered=False, gone=False)


def test_private_key_never_in_result_repr() -> None:
    # SC-009: the result object never carries the secret.
    assert "PRIVATE" not in repr(PushResult(delivered=True, gone=False))
