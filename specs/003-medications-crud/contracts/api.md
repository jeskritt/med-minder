# API Contracts: Medications CRUD

## Endpoints

### `GET /api/v1/medications`
Returns a list of all active (non-soft-deleted) medications for the authenticated user.
**Response**: `200 OK`
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Ibuprofen",
      "dosage": "200",
      "unit": "mg",
      "times_per_day": 2,
      "start_date": "2026-05-01",
      "end_date": "2026-05-10",
      "total_doses": null,
      "refill_count": 30,
      "refill_threshold": 5,
      "schedules": [{"id": "uuid", "time_of_day": "08:00"}, {"id": "uuid", "time_of_day": "20:00"}]
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
  "dosage": "200",
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
**Response**: `201 Created`

### `PUT /api/v1/medications/{id}`
Updates an existing medication and replaces its inline schedules.
**Request Body**: Same as POST.
**Response**: `200 OK`

### `DELETE /api/v1/medications/{id}`
Soft-deletes a medication.
**Response**: `204 No Content`
