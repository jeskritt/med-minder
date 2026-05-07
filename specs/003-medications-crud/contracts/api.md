# API Contracts: Medications CRUD

> **Reconciliation note (2026-05-07):** field names match the existing Phase 1
> schema (`quantity_per_dose`, not `dosage`). All endpoints require an
> authenticated session (the `mm_session` cookie). All responses are scoped to
> the current user.

## Endpoints

### `GET /api/v1/medications`

Returns all non-soft-deleted medications for the authenticated user, with
their current schedules.

**Response**: `200 OK`

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Ibuprofen",
      "quantity_per_dose": "200.000",
      "unit": "mg",
      "times_per_day": 2,
      "start_date": "2026-05-01",
      "end_date": "2026-05-10",
      "total_doses": null,
      "refill_count": 30,
      "refill_threshold": 5,
      "schedules": [
        {"id": "uuid", "time_of_day": "08:00:00"},
        {"id": "uuid", "time_of_day": "20:00:00"}
      ]
    }
  ]
}
```

### `POST /api/v1/medications`

Creates a new medication and its inline schedules.

**Request Body**:

```json
{
  "name": "Ibuprofen",
  "quantity_per_dose": "200",
  "unit": "mg",
  "times_per_day": 2,
  "start_date": "2026-05-01",
  "end_date": "2026-05-10",
  "total_doses": null,
  "schedules": ["08:00", "20:00"],
  "refill_count": 30,
  "refill_threshold": 5
}
```

**Response**: `201 Created`, body matches the `GET` item shape.

### `PUT /api/v1/medications/{id}`

Updates an existing medication and replaces its inline schedules
(complete-replacement strategy: previously-linked schedules are
soft-deleted and the join rows are removed before new ones are created).

**Request Body**: same as `POST`.
**Response**: `200 OK`, body matches the `GET` item shape.
**Errors**: `404` if the medication does not belong to the current user
or is already soft-deleted.

### `DELETE /api/v1/medications/{id}`

Soft-deletes a medication (sets `deleted_at = now()`). Idempotent:
re-deleting an already-deleted medication still returns `204`.

**Response**: `204 No Content`.
**Errors**: `404` if the medication does not belong to the current user.
