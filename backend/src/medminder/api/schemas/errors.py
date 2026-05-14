"""Wire-format error bodies."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MinIntervalViolation(BaseModel):
    """HTTP 409 body when a count_down med's interval has not elapsed."""

    model_config = ConfigDict(extra="forbid")

    code: Literal["min_interval_not_elapsed"]
    medication_id: uuid.UUID
    next_allowed_at: datetime
    remaining_seconds: int = Field(ge=1)


__all__ = ["MinIntervalViolation"]
