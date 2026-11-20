"""Pydantic schemas for the push-subscription router (Phase 7)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from medminder.domain.push import InvalidPushEndpointError, validate_push_endpoint


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

    @field_validator("endpoint")
    @classmethod
    def _validate_endpoint(cls, value: str) -> str:
        try:
            return validate_push_endpoint(value)
        except InvalidPushEndpointError as exc:
            raise ValueError(str(exc)) from exc


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
