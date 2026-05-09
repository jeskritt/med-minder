# Phase 5 Quickstart — verifying timer modes end-to-end

These recipes are the per-user-story acceptance harness. They assume
`just dev` is running and a user `demo@example.com` exists (create
via `medminder-admin user add` if not — see Phase 1 quickstart for
that flow).

The recipes use `curl` and `pnpm` so they work identically on
Windows (Git Bash / WSL) and Linux.

---

## Login (shared by all three flows)

```bash
# Capture the session cookie used by the rest of the recipes.
curl -sS -c /tmp/mm_cookies.txt \
  -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"demo-password-12chars"}'
```

---

## US1 — Migraine Molly (count-up)

**Goal**: see a server-authoritative count-up timer that ticks in the
client and survives a page reload.

```bash
# 1. Create a count_up medication via the admin path (the FE form is the
#    canonical path; this recipe uses the API directly so verification
#    fits in a script).
curl -sS -b /tmp/mm_cookies.txt \
  -X POST http://localhost:8000/api/v1/medications \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "Sumatriptan",
        "times_per_day": 1,
        "quantity_per_dose": "1.000",
        "unit": "tablet",
        "timer_preference": "count_up"
      }' | tee /tmp/molly_med.json

MED_ID=$(jq -r .id /tmp/molly_med.json)

# 2. Mark a dose.
curl -sS -b /tmp/mm_cookies.txt \
  -X POST http://localhost:8000/api/doses \
  -H 'Content-Type: application/json' \
  -d "{\"medication_id\":\"$MED_ID\"}"

# 3. Read the today endpoint and inspect timer_state.
curl -sS -b /tmp/mm_cookies.txt http://localhost:8000/api/schedules/today \
  | jq ".items[] | select(.medication_id==\"$MED_ID\") | .timer_state"
```

**Expected**: `timer_state` shows
`{"mode":"count_up","as_of":"...","last_dose_at":"...","elapsed_seconds":<small int>}`.
`elapsed_seconds` increases on each subsequent GET. Open the today
view in the browser at `http://localhost:5173/today` — the displayed
elapsed time advances at least once per minute without a page
reload, and reloading the page resumes from the server-supplied
value (no jump or reset).

---

## US2 — Headache Harry (count-down + min-interval guard)

**Goal**: see the server reject a too-soon dose with HTTP 409 and a
structured body. **This is the SC-002 acceptance test.**

```bash
# 1. Create a count_down medication with a 60-minute interval.
curl -sS -b /tmp/mm_cookies.txt \
  -X POST http://localhost:8000/api/v1/medications \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "Ibuprofen 200",
        "times_per_day": 4,
        "quantity_per_dose": "1.000",
        "unit": "tablet",
        "timer_preference": "count_down",
        "min_interval_minutes": 60
      }' | tee /tmp/harry_med.json

MED_ID=$(jq -r .id /tmp/harry_med.json)

# 2. Mark the first dose. Should succeed (201).
curl -sS -i -b /tmp/mm_cookies.txt \
  -X POST http://localhost:8000/api/doses \
  -H 'Content-Type: application/json' \
  -d "{\"medication_id\":\"$MED_ID\"}"

# 3. Try to mark a second dose immediately. Should FAIL with 409.
curl -sS -i -b /tmp/mm_cookies.txt \
  -X POST http://localhost:8000/api/doses \
  -H 'Content-Type: application/json' \
  -d "{\"medication_id\":\"$MED_ID\"}"
```

**Expected**: Step 3 returns `HTTP/1.1 409 Conflict` with body:

```json
{
  "code": "min_interval_not_elapsed",
  "medication_id": "...",
  "next_allowed_at": "2026-05-08T...Z",
  "remaining_seconds": 3590
}
```

The browser at `http://localhost:5173/today` shows the
mark-as-taken control disabled with "Next dose in 59m 50s" (or
similar) ticking down. When the timer reaches zero, the control
becomes enabled and a single short haptic vibration fires (mobile
devices, foreground only — FR-010).

---

## US3 — Billy Bat (multi-sub-dose window)

**Goal**: confirm window arithmetic, the "Dose available" CTA logic,
and the FR-008b passive banner.

```bash
# 1. Create a multi_sub_dose medication: 3 sub-doses in a 6-hour window.
curl -sS -b /tmp/mm_cookies.txt \
  -X POST http://localhost:8000/api/v1/medications \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "Tylenol 3",
        "times_per_day": 3,
        "quantity_per_dose": "1.000",
        "unit": "tablet",
        "timer_preference": "multi_sub_dose",
        "window_duration_minutes": 360
      }' | tee /tmp/billy_med.json

MED_ID=$(jq -r .id /tmp/billy_med.json)

# 2. Mark the first sub-dose. Inspect detail.
curl -sS -b /tmp/mm_cookies.txt \
  -X POST http://localhost:8000/api/doses \
  -H 'Content-Type: application/json' \
  -d "{\"medication_id\":\"$MED_ID\"}"

curl -sS -b /tmp/mm_cookies.txt \
  "http://localhost:8000/api/v1/medications/$MED_ID" \
  | jq .timer_state
```

**Expected**: `timer_state` shows
`{"mode":"multi_sub_dose","active_window":{"slots_total":3,"slots_used":1,...},"previous_window_unused_slots":0, ...}`.

```bash
# 3. Mark a second sub-dose. slots_used should be 2.
# 4. Mark a third sub-dose. The detail should now report slots_used=3.
# 5. Attempt a fourth dose immediately. The mark-as-taken endpoint
#    should reject the request with HTTP 409 (window full).
```

To exercise the **passive banner** (FR-008b) without waiting six
hours, the simplest path is to insert a row into `doses` with a
backdated `taken_at` via the database. In a developer shell:

```bash
psql -h localhost -U medminder_app -d medminder -c "
  INSERT INTO doses (id, user_id, medication_id, schedule_id, taken_at, quantity, created_at)
  VALUES (gen_random_uuid(), '<user_id>', '$MED_ID', NULL,
          NOW() - INTERVAL '7 hours', 1.0, NOW() - INTERVAL '7 hours');
"
```

Then GET the detail again — `previous_window_unused_slots` should
be `2` (the inserted backdated dose started a window 7h ago that
expired 1h ago with 2 of 3 slots unused). The browser at
`http://localhost:5173/medications/$MED_ID` shows a passive banner
("Last window ended with 2 of 3 slots unused — tap when ready") and
the mark-as-taken control reads "Dose available." Tapping it clears
the banner and opens a fresh window.

---

## Coverage check (SC-005)

```bash
just test                       # Backend pytest + frontend vitest
cat backend/coverage.xml | grep 'line-rate' | head -1   # project-wide
just test 2>&1 | grep 'medminder/domain/timers'         # module floor
```

**Expected**: project line-rate ≥ 0.85; `domain/timers.py` line-rate
≥ 0.95; no module below 0.70.

## E2E check (SC-006)

```bash
cd frontend && pnpm playwright test timer-modes.spec.ts
```

**Expected**: the count-down zero-boundary scenario passes — the
button-enabled state on the client matches the server's accept/reject
verdict at the moment of the boundary crossing.
