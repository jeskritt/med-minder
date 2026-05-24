"""Pydantic schemas for the push-subscription router (Phase 7)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VapidKeyOut(BaseModel):
    """Public VAPID application-server key for the browser."""

    model_config = ConfigDict(extra="forbid")

    public_key: str


class PushKeys(BaseModel):
    """The client keys from a browser ``PushSubscription``."""

    model_config = ConfigDict(extra="forbid")

    p256dh: str = Field(min_length=1, max_length=512)
    auth: str = Field(min_length=1, max_length=512)


class PushSubscriptionIn(BaseModel):
    """Inbound body for ``POST /api/v1/push/subscriptions``."""

    model_config = ConfigDict(extra="forbid")

    endpoint: str = Field(min_length=1, max_length=2048)
    keys: PushKeys


class PushUnsubscribeIn(BaseModel):
    """Inbound body for ``DELETE /api/v1/push/subscriptions``."""

    model_config = ConfigDict(extra="forbid")

    endpoint: str = Field(min_length=1, max_length=2048)


__all__ = [
    "PushKeys",
    "PushSubscriptionIn",
    "PushUnsubscribeIn",
    "VapidKeyOut",
]
