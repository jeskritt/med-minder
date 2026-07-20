"""Web Push delivery via pywebpush (Phase 7, FR-007/FR-016).

``pywebpush`` is synchronous, so each send runs in a worker thread and
never blocks the dispatch tick / event loop. Delivery is best-effort: a
``404``/``410`` from the push service means the subscription is permanently
gone and the caller should delete it; any other failure is swallowed so a
single bad subscription can't abort the batch.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

# pywebpush ships no type stubs and is not py.typed; this is the single
# isolated import-untyped suppression for the feature (Principle II).
from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]

from medminder.db.models import PushSubscription
from medminder.domain.crypto import InvalidToken, build_fernet, decrypt_secret
from medminder.settings import Settings

logger = logging.getLogger(__name__)

_warned_unconfigured = False


def _host(subscription: PushSubscription) -> str | None:
    """Push-service hostname, for logs.

    The endpoint path carries a per-device secret token, so only the host is
    ever logged — enough to tell FCM from Mozilla, useless to an attacker.
    """
    return urlsplit(subscription.endpoint).hostname


@dataclass(frozen=True)
class PushResult:
    """Outcome of one push send."""

    delivered: bool
    gone: bool
    """``True`` when the push service reports the endpoint permanently
    invalid (HTTP 404/410) — the subscription should be deleted (FR-016)."""


async def send_web_push(
    *,
    subscription: PushSubscription,
    payload: dict[str, Any],
    settings: Settings,
) -> PushResult:
    """Send one Web Push message. Never raises.

    When VAPID keys are unconfigured (dev/test), the send is skipped
    (``delivered=False, gone=False``) — reminders are still recorded and
    visible in-app. The VAPID private key is used only to sign here and is
    never returned or logged (FR-002).
    """
    if not settings.vapid_private_key:
        global _warned_unconfigured
        if not _warned_unconfigured:
            _warned_unconfigured = True
            logger.warning(
                "web push disabled: VAPID_PRIVATE_KEY is unset — reminders "
                "will be in-app only"
            )
        return PushResult(delivered=False, gone=False)

    # Decrypt the at-rest key material (ADR-0020).  A row written before
    # encryption — or under a now-rotated key — won't decrypt: treat it as a
    # dead subscription so the caller deletes it and the browser re-subscribes.
    fernet = build_fernet(settings)
    try:
        p256dh = decrypt_secret(fernet, subscription.p256dh)
        auth = decrypt_secret(fernet, subscription.auth)
    except InvalidToken:
        # Legacy plaintext row, or written under a since-rotated key.  Log the
        # endpoint host only — never the token or key material.
        logger.warning(
            "push subscription key material failed to decrypt "
            "(legacy plaintext or rotated PUSH_ENCRYPTION_KEY): host=%s",
            _host(subscription),
        )
        return PushResult(delivered=False, gone=True)

    def _send() -> None:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": p256dh,
                    "auth": auth,
                },
            },
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )

    attempts = max(1, settings.reminder_send_max_attempts)
    for attempt in range(1, attempts + 1):
        try:
            await asyncio.to_thread(_send)
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
            if status in (404, 410):
                # Permanently gone — don't retry; caller deletes it (FR-016).
                logger.info(
                    "push endpoint gone (HTTP %s): host=%s",
                    status,
                    _host(subscription),
                )
                return PushResult(delivered=False, gone=True)
            logger.warning(
                "push send failed (HTTP %s), attempt %d/%d: host=%s",
                status,
                attempt,
                attempts,
                _host(subscription),
            )
            if attempt >= attempts:
                return PushResult(delivered=False, gone=False)
        except Exception:
            # Best-effort: transient/network errors must not break the tick.
            logger.exception(
                "push send errored, attempt %d/%d: host=%s",
                attempt,
                attempts,
                _host(subscription),
            )
            if attempt >= attempts:
                return PushResult(delivered=False, gone=False)
        else:
            return PushResult(delivered=True, gone=False)
    return PushResult(delivered=False, gone=False)


__all__ = ["PushResult", "send_web_push"]
