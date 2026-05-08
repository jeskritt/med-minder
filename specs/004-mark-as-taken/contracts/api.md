# API Contracts: mark-as-taken

All endpoints require an authenticated session (Phase 2). The
`user_id` recorded on every write is derived from the session — never
accepted from the request body.

Responses use the project-wide error envelope established in Phase 2;
only the status codes specific to each endpoint are listed below.

## `POST /api/doses`

Record a medication-taken event.

**Request body**

```json
{
  "medication_id": "uuid",
  "schedule_id": "uuid | null",
  "taken_at": "2026-05-07T14:30:00Z",
  "quantity": "0.500"
}
```

| Field           | Required                                              | Notes                                                                              |
| --------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `medication_id` | yes                                                   | Must belong to the session user.                                                   |
| `schedule_id`   | yes when from the Today view; otherwise omit or null | When set, must belong to the user and be linked to `medication_id` via `schedule_medications`. |
| `taken_at`      | yes                                                   | ISO 8601 instant with offset.                                                      |
| `quantity`      | no                                                    | Decimal string; defaults to `medications.quantity_per_dose` when omitted.          |

**Responses**

- `201 Created` — body is the created dose:

  ```json
  {
    "id": "uuid",
    "medication_id": "uuid",
    "schedule_id": "uuid | null",
    "taken_at": "2026-05-07T14:30:00Z",
    "quantity": "0.500",
    "created_at": "2026-05-07T14:30:05Z"
  }
  ```

- `403 Forbidden` — `medication_id` does not belong to the session user.
- `422 Unprocessable Entity` — `schedule_id` is not linked to the medication, the medication is soft-deleted, `quantity <= 0`, or any other validation failure.

## `POST /api/doses/{dose_id}/void`

Record a compensating "un-take" event. Phase 1 D6 prohibits
hard-deleting from `doses`; this endpoint inserts into `dose_voids`
instead. The original `doses` row is left untouched.

**Request body** — empty.

**Responses**

- `204 No Content` — void recorded.
- `403 Forbidden` — dose belongs to a different user.
- `404 Not Found` — dose does not exist.
- `409 Conflict` — dose has already been voided (`dose_voids.dose_id` is `UNIQUE`).

## `GET /api/schedules/today`

List the user's scheduled medication slots for "today" in their
timezone, with the effective dose for each slot if one exists.

**Query parameters**

| Name       | Type     | Required | Notes                                                                                |
| ---------- | -------- | -------- | ------------------------------------------------------------------------------------ |
| `timezone` | string   | no       | IANA zone name. Overrides `users.timezone`; falls back to it when omitted.           |
| `date`     | `YYYY-MM-DD` | no  | Target date in the chosen zone. Defaults to "today" in that zone. (Test/debug aid.) |

**Response `200 OK`**

```json
{
  "date": "2026-05-07",
  "timezone": "America/Los_Angeles",
  "items": [
    {
      "schedule_id": "uuid",
      "medication_id": "uuid",
      "name": "Lisinopril",
      "scheduled_time": "08:00",
      "quantity_per_dose": "10.000",
      "unit": "mg",
      "dose": null
    },
    {
      "schedule_id": "uuid",
      "medication_id": "uuid",
      "name": "Metformin",
      "scheduled_time": "20:00",
      "quantity_per_dose": "500.000",
      "unit": "mg",
      "dose": {
        "id": "uuid",
        "taken_at": "2026-05-07T15:12:33Z"
      }
    }
  ]
}
```

**Semantics**

- Each item is one **scheduled slot**. A medication attached to two
  schedules that both fire today appears twice. The
  `(schedule_id, medication_id)` pair is the stable row key the UI
  should use as React `key`.
- `dose` is the most recent **effective** dose for that
  `(schedule_id, medication_id)` within today's UTC bounds. "Effective"
  means a row in `doses` with no matching row in `dose_voids`.
- Voided doses are excluded; `dose_voids` rows are not exposed in this
  response.
- Soft-deleted medications and schedules (`deleted_at IS NOT NULL`) are
  excluded.

**Responses**

- `200 OK` — body as above.
- `400 Bad Request` — `timezone` is not a recognized IANA zone, or `date` is malformed.

## Out of scope for these contracts

- An ad-hoc dose history endpoint (`GET /api/doses?...`) — adherence
  views land in Phase 9.
- Reminder/snooze endpoints — Phase 7.
- Cooldown / interaction checks before allowing a dose — Phase 6.
