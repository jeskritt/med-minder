"""Push-subscription router (Phase 7) — VAPID key + register/remove.

All routes are scoped to the logged-in user (FR-001/FR-017). The VAPID
private key is never exposed; only the public key is served (FR-002).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_current_user, get_session, get_settings
from medminder.api.schemas.push import (
    PushSubscriptionIn,
    PushUnsubscribeIn,
    VapidKeyOut,
)
from medminder.db.models import PushSubscription, User
from medminder.domain.crypto import build_fernet, encrypt_secret
from medminder.settings import Settings

router = APIRouter(prefix="/api/v1/push", tags=["push"])


@router.get("/vapid-public-key", response_model=VapidKeyOut)
async def get_vapid_public_key(
    _user: User = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> VapidKeyOut:
    """Return the public VAPID key for browser subscription (FR-002).

    Auth-gated (single-tenant): nothing is served pre-login. The private
    key is never exposed.
    """
    return VapidKeyOut(public_key=settings.vapid_public_key)


@router.post("/subscriptions")
async def register_subscription(
    body: PushSubscriptionIn,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    """Idempotently register this device's subscription (FR-001).

    New endpoint → 201; an existing ``(user, endpoint)`` → keys refreshed, 200.
    The ``p256dh``/``auth`` key material is encrypted at rest (ADR-0020); the
    ``endpoint`` stays plaintext as it is the lookup + unique-constraint key.
    """
    fernet = build_fernet(settings)
    p256dh = encrypt_secret(fernet, body.keys.p256dh)
    auth = encrypt_secret(fernet, body.keys.auth)
    existing = (
        await db.execute(
            select(PushSubscription).where(
                PushSubscription.user_id == user.id,
                PushSubscription.endpoint == body.endpoint,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.p256dh = p256dh
        existing.auth = auth
        await db.flush()
        return Response(status_code=status.HTTP_200_OK)
    db.add(
        PushSubscription(
            user_id=user.id,
            endpoint=body.endpoint,
            p256dh=p256dh,
            auth=auth,
        )
    )
    await db.flush()
    return Response(status_code=status.HTTP_201_CREATED)


@router.delete("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def remove_subscription(
    body: PushUnsubscribeIn,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Remove this device's subscription (idempotent, user-scoped)."""
    await db.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == body.endpoint,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
