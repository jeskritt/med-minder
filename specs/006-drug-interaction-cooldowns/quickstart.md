# Phase 6 Quickstart — verifying drug-interaction cooldowns end-to-end

These recipes are the per-user-story acceptance harness. They assume
`just dev` is running and a user `demo@example.com` exists (create via
`medminder-admin user add` if not). `curl` + `jq` are used so the
recipes work identically on Windows (Git Bash / WSL) and Linux.

---

## Phase A — Baseline sanity gate (run FIRST, before any Phase 6 change)

Confirm a clean baseline so later drift is unambiguously Phase 6's:

```bash
# 1. OpenAPI client is in sync (working tree clean afterward).
just generate-client          # PowerShell-direct: python scripts/generate_openapi_client.py
git status --porcelain frontend/src/api/v1.d.ts   # expect: no output

# 2. Models match the last migration (no pre-existing autogen drift).
cd backend && python -m alembic check && cd ..
```

Both mirror the CI gate (`.github/workflows/ci.yml`: `alembic upgrade
head` → `alembic check`, then the OpenAPI drift check). If either is
dirty, fix that before starting Phase 6.

After the Phase 6 migration is added, re-run:

```bash
just migrate                  # alembic upgrade head
cd backend && python -m alembic check && cd ..   # expect: empty diff
just generate-client          # regenerate v1.d.ts after schema changes
```

---

## Login (shared by all flows)

```bash
curl -sS -c /tmp/mm_cookies.txt \
  -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"demo-password-12chars"}'
```

Create two medications to pair (A = migraine med, B = ibuprofen):

```bash
curl -sS -b /tmp/mm_cookies.txt -X POST http://localhost:8000/api/v1/medications \
  -H 'Content-Type: application/json' \
  -d '{"name":"Sumatriptan","times_per_day":1,"quantity_per_dose":"1.000","unit":"tablet","timer_preference":"none"}' \
  | tee /tmp/med_a.json
curl -sS -b /tmp/mm_cookies.txt -X POST http://localhost:8000/api/v1/medications \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ibuprofen 200","times_per_day":4,"quantity_per_dose":"1.000","unit":"tablet","timer_preference":"none"}' \
  | tee /tmp/med_b.json
A=$(jq -r .id /tmp/med_a.json); B=$(jq -r .id /tmp/med_b.json)
```

---

## US3 — Author a symmetric rule (run first; US1/US2 need a rule)

**Goal**: create an A↔B rule from the medication form's "Conflicts
with" section; confirm symmetry and removal. **SC-006.**

```bash
# Create the symmetric rule (120-minute cooldown).
curl -sS -i -b /tmp/mm_cookies.txt \
  -X POST "http://localhost:8000/api/v1/medications/$A/interactions" \
  -H 'Content-Type: application/json' \
  -d "{\"other_medication_id\":\"$B\",\"cooldown_minutes\":120}"

# List rules for B — the same row appears (symmetric, matched either order).
curl -sS -b /tmp/mm_cookies.txt \
  "http://localhost:8000/api/v1/medications/$B/interactions" | jq .

# Duplicate unordered pair → 409.
curl -sS -i -b /tmp/mm_cookies.txt \
  -X POST "http://localhost:8000/api/v1/medications/$B/interactions" \
  -H 'Content-Type: application/json' \
  -d "{\"other_medication_id\":\"$A\",\"cooldown_minutes\":90}"

# Self-pair / non-positive cooldown → 422.
curl -sS -i -b /tmp/mm_cookies.txt \
  -X POST "http://localhost:8000/api/v1/medications/$A/interactions" \
  -H 'Content-Type: application/json' \
  -d "{\"other_medication_id\":\"$A\",\"cooldown_minutes\":0}"
```

**Expected**: create → `201`; B's list shows the same rule;
duplicate → `409`; self-pair/zero → `422`. In the browser, open
medication A's edit form (`/medications/$A/edit`): the **"Conflicts
with"** section lists the B rule with a remove button; "Add
interaction" appends a row whose selector offers only the user's own
non-deleted meds, excluding A and already-paired meds. Removing the
row and saving deletes the rule (changing a cooldown = remove +
re-add; there is no in-place edit).

---

## US1 — Warned, then explicitly confirms a conflicting dose

**Goal**: server-authoritative warn + override + audited record.
**SC-001 / SC-003.**

```bash
# 1. Mark A as taken (first dose of the pair never warns).
curl -sS -i -b /tmp/mm_cookies.txt -X POST http://localhost:8000/api/doses \
  -H 'Content-Type: application/json' -d "{\"medication_id\":\"$A\"}"

# 2. Attempt B WITHOUT acknowledgment, directly to the API (frontend bypass).
curl -sS -i -b /tmp/mm_cookies.txt -X POST http://localhost:8000/api/doses \
  -H 'Content-Type: application/json' -d "{\"medication_id\":\"$B\"}"

# 3. Retry B WITH acknowledgment.
curl -sS -i -b /tmp/mm_cookies.txt -X POST http://localhost:8000/api/doses \
  -H 'Content-Type: application/json' \
  -d "{\"medication_id\":\"$B\",\"interaction_acknowledged\":true}"
```

**Expected**:
- Step 1 → `201`.
- Step 2 → `HTTP/1.1 409 Conflict`, no `doses` row for B, body:

  ```json
  {
    "code": "interaction_cooldown_active",
    "medication_id": "<B>",
    "conflicts": [
      {"conflicting_medication_id":"<A>","conflicting_medication_name":"Sumatriptan",
       "cooldown_elapses_at":"...Z","remaining_seconds": 7100}
    ],
    "cooldown_elapses_at": "...Z",
    "remaining_seconds": 7100
  }
  ```
  `code` is distinct from `min_interval_not_elapsed` / `window_full`.
- Step 3 → `201`; a `dose_interaction_overrides` row exists for the
  new B dose referencing A. Verify:

  ```bash
  psql -h localhost -U medminder_app -d medminder -c \
    "SELECT dose_id, conflicting_medication_id FROM dose_interaction_overrides;"
  ```

Browser: marking B on `/today` shows an explicit "take anyway"
confirmation (the conflict is never a dead-end, unlike a Phase 5
overdose 409); confirming records the dose.

---

## US2 — Conflict context + live cooldown timer

**Goal**: legible, server-seeded, self-clearing indicator. **SC-002 /
SC-004 / SC-005.**

```bash
# With A taken in US1 and the A↔B rule active:
curl -sS -b /tmp/mm_cookies.txt http://localhost:8000/api/schedules/today \
  | jq ".items[] | select(.medication_id==\"$B\") | .interaction_state"
curl -sS -b /tmp/mm_cookies.txt "http://localhost:8000/api/v1/medications/$B" \
  | jq .interaction_state
```

**Expected**: `interaction_state` is non-null and names A with a
positive `remaining_seconds`; on repeated GETs `remaining_seconds`
decreases. Browser at `/today`: B shows "Interacts with Sumatriptan —
safe at H:MM" with the remaining time ticking down at least once per
visible minute (client counter seeded from `as_of`, no polling) and
surviving a page reload (server-authoritative).

Clearing — either path, no manual reload:

```bash
# (a) Void A's arming dose (Phase 4 un-take), then refetch.
DOSE_A=$(curl -sS -b /tmp/mm_cookies.txt \
  "http://localhost:8000/api/v1/medications/$A" | jq -r '.last_dose_id // empty')
curl -sS -i -b /tmp/mm_cookies.txt -X POST "http://localhost:8000/api/doses/$DOSE_A/void"
curl -sS -b /tmp/mm_cookies.txt http://localhost:8000/api/schedules/today \
  | jq ".items[] | select(.medication_id==\"$B\") | .interaction_state"   # → null
```

Or (b) let the 120-minute cooldown elapse (or seed a backdated A dose
via `psql` as in the Phase 5 quickstart) and refetch — `interaction_state`
becomes `null` and marking B no longer requires the confirm step.

---

## Cross-user isolation (FR-019)

```bash
# As a SECOND user, GET the first user's medication ids → 404; the
# first user's rules/overrides/conflicts never appear in the second
# user's today/list/detail responses.
```

Covered by `backend/tests/api/test_interaction_state.py` and
`test_medication_interactions_api.py` (cross-user negative).

---

## Coverage check (SC-009)

```bash
just test                                               # backend pytest + frontend vitest
cat backend/coverage.xml | grep 'line-rate' | head -1   # project-wide ≥ 0.85
just test 2>&1 | grep 'medminder/domain/interactions'   # module ≥ 0.95
```

**Expected**: project line-rate ≥ 0.85; `domain/interactions.py`
≥ 0.95; no module below 0.70.

## Typing / lint gate

```bash
just typecheck     # mypy --strict + tsc --noEmit
just lint          # ruff + eslint + prettier --check
```

**Expected**: all clean (Constitution Principle II / V).
