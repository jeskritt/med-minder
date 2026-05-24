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
from dataclasses import dataclass
from typing import Any

# pywebpush ships no type stubs and is not py.typed; this is the single
# isolated import-untyped suppression for the feature (Principle II).
from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]

from medminder.db.models import PushSubscription
from medminder.settings import Settings


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
        return PushResult(delivered=False, gone=False)

    def _send() -> None:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh,
                    "auth": subscription.auth,
                },
            },
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )

    try:
        await asyncio.to_thread(_send)
    except WebPushException as exc:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        return PushResult(delivered=False, gone=status in (404, 410))
    except Exception:
        # Best-effort: transient/network errors must not break the tick.
        return PushResult(delivered=False, gone=False)
    return PushResult(delivered=True, gone=False)


__all__ = ["PushResult", "send_web_push"]
