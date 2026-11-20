"""``/api/v1/adherence`` — read-only adherence views (Phase 9).

Two endpoints, both scoped to the authenticated user's own data:

- ``GET /medications/{id}`` — per-day status + window % + course progress.
- ``GET /export.csv`` — full non-voided dose history as a CSV attachment.

Thin transport over ``domain.adherence`` (ADR-0016). No data is written.
"""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Iterator
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from medminder.api.deps import get_current_user, get_session
from medminder.api.schemas.adherence import (
    MedicationAdherenceOut,
    to_medication_adherence_out,
)
from medminder.db.models import User
from medminder.domain.adherence import (
    AdherenceRangeError,
    ExportRow,
    MedicationNotFoundError,
    compute_medication_adherence,
    iter_export_rows,
)
from medminder.domain.timezone import InvalidTimezoneError

router = APIRouter(prefix="/api/v1/adherence", tags=["adherence"])

_CSV_HEADER = [
    "medication_name",
    "taken_at",
    "quantity",
    "unit",
    "schedule_label",
    "soft_deleted",
]


@router.get("/medications/{medication_id}", response_model=MedicationAdherenceOut)
async def get_medication_adherence(
    medication_id: uuid.UUID,
    from_: date = Query(alias="from"),  # noqa: B008
    to: date = Query(),  # noqa: B008
    timezone: str | None = Query(default=None),
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> MedicationAdherenceOut:
    """Per-day adherence for one medication over ``[from, to]`` (inclusive)."""
    try:
        result = await compute_medication_adherence(
            db,
            user=user,
            medication_id=medication_id,
            from_date=from_,
            to_date=to,
            timezone_override=timezone,
        )
    except MedicationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except AdherenceRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except InvalidTimezoneError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown IANA timezone: {exc}",
        ) from exc
    return to_medication_adherence_out(result)


_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: str) -> str:
    """Neutralize spreadsheet formula injection in user-authored CSV cells."""
    if value and value.startswith(_CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def _csv_lines(rows: list[ExportRow]) -> Iterator[str]:
    """Yield CSV text one row at a time (header first)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def flush() -> str:
        value = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return value

    writer.writerow(_CSV_HEADER)
    yield flush()
    for row in rows:
        writer.writerow(
            [
                _csv_safe(row.medication_name),
                row.taken_at.isoformat(),
                str(row.quantity),
                _csv_safe(row.unit),
                _csv_safe(row.schedule_label),
                "true" if row.soft_deleted else "false",
            ]
        )
        yield flush()


@router.get("/export.csv")
async def export_dose_history_csv(
    from_: date | None = Query(default=None, alias="from"),  # noqa: B008
    to: date | None = Query(default=None),  # noqa: B008
    timezone: str | None = Query(default=None),
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> StreamingResponse:
    """Stream the caller's non-voided dose history as a CSV attachment.

    Optional ``from``/``to`` (inclusive local days) bound the export; both
    omitted exports the full history.
    """
    try:
        rows = await iter_export_rows(
            db,
            user=user,
            timezone_override=timezone,
            from_date=from_,
            to_date=to,
        )
    except AdherenceRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except InvalidTimezoneError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown IANA timezone: {exc}",
        ) from exc
    return StreamingResponse(
        _csv_lines(rows),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="medminder-doses.csv"'
        },
    )
