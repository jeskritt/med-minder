# Quickstart — Long-term adherence views (Phase 9)

How to exercise and verify this feature. Assumes the stack is up (`just dev`) and you are
logged in as a user with at least one scheduled medication and some dose history.

## 1. Manual (UI) verification

1. **Calendar** — Open a medication's detail page (`/medications/<id>`). The adherence
   section shows a month calendar. Confirm:
   - A past day where all scheduled doses were taken is **green + check icon**.
   - A past day with some-but-not-all taken is **yellow + dash icon**.
   - A past scheduled day with nothing taken (past the 4h tolerance) is **red + cross icon**.
   - A day before `start_date` / after `end_date`, or a weekday the schedule doesn't cover,
     is **inactive (white/neutral)** and not red.
   - A future scheduled day is **gray**.
   - Every cell has a non-color icon, not color alone (SC-005).
   - Paging to previous months re-renders correctly (US1).
2. **Adherence %** — Confirm a numeric percentage shows for the visible window on a scheduled
   med, and is **absent** on a PRN/as-needed med (FR-017).
3. **Trend** — Toggle to the stacked-bar view; confirm one bar per day, height = scheduled
   count, segments colored taken/missed; switch week ⇄ month (US3).
4. **Course progress** — On a med with a course size, confirm "N of M" and a "complete" state
   once reached; void a dose and confirm the count drops; a med with no course size shows no
   progress (US2). Confirm completion does **not** change reminders or the med (display-only).
5. **CSV export** — Use the Export action on the medications list; open the downloaded file in
   a spreadsheet. Confirm one row per non-voided dose with
   `medication_name, taken_at, quantity, unit, schedule_label, soft_deleted`, and that a
   soft-deleted med appears with " (removed)" (US4 / UC-6.3).

## 2. API verification

```bash
# Per-medication adherence for a month (cookie auth; -b cookies.txt from login)
curl -s -b cookies.txt \
  "http://localhost:8000/api/v1/adherence/medications/<MED_ID>?from=2026-05-01&to=2026-05-31" | jq

# Expect: { medication_id, timezone, from, to, days:[{date,expected,taken,status}...],
#           adherence_pct, course: {total,taken,complete} | null }

# CSV export
curl -s -b cookies.txt "http://localhost:8000/api/v1/adherence/export.csv" -D - | head

# Expect: Content-Type: text/csv; Content-Disposition: attachment; filename="medminder-doses.csv"
# then the header row + one row per non-voided dose.

# Cross-user isolation: another user's medication id → 404 (not 200 with data).
# Anonymous (no cookie) → 401.
```

## 3. Automated checks

```bash
# Backend domain classification matrix + endpoints (real Postgres)
cd backend && python -m pytest tests/domain/test_adherence.py tests/api/test_adherence_api.py tests/api/test_adherence_export.py -v

# Frontend component tests
cd frontend && pnpm test -- AdherenceCalendar AdherenceTrend CourseProgress

# Full gates
just typecheck   # mypy --strict + tsc --noEmit
just test        # pytest (coverage >= 85%) + vitest
just lint        # ruff + eslint + prettier --check
just generate-client   # regenerate api/v1.d.ts; CI fails on drift
```

## 4. Acceptance mapping

| Spec item | Verified by |
|---|---|
| US1 calendar (taken/partial/missed/future/inactive) | Manual §1.1; `test_adherence.py`; `AdherenceCalendar.test.tsx` |
| FR-002 / SC-005 non-color signal | Manual §1.1; `AdherenceCalendar.test.tsx` |
| FR-004 4h missed tolerance | `test_adherence.py` |
| FR-006 PRN never missed | `test_adherence.py`; Manual §1.2 |
| FR-007/008 course progress + completion | Manual §1.4; `test_adherence.py`; `CourseProgress.test.tsx` |
| FR-008 completion is display-only | Manual §1.4 |
| FR-010 trend view | Manual §1.3; `AdherenceTrend.test.tsx` |
| FR-011/012 CSV + removed marking | Manual §1.5; `test_adherence_export.py` |
| FR-013 current-TZ bucketing | `test_adherence.py` |
| FR-015 own-data-only | `test_adherence_api.py` (404/401) |
| FR-017 numeric % (null for PRN) | Manual §1.2; `test_adherence_api.py` |
