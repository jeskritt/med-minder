# Design — Timer modes

This is exploratory design thinking, not a binding spec. The
authoritative behavior lives in `docs/user_stories.md` UC-3 / UC-4
and the implementation in Phase 5. The state-machine *architecture*
decision lives in `docs/adr/0004-timer-state-machines.md`.

## The four modes

Mapping from persona need to timer behavior:

### Mode `none` — Granny Smith
No clock at all. A boolean "taken today" flag that flips when the
user marks a dose, with a very obvious visual indicator and a
timestamp shown next to it. Tapping again opens the un-take
confirmation modal (UC-4.2).

This is the simplest mode and the one the most users will need.
Everything else exists to handle medications that *can't* be modeled
as "did you do the thing today?"

### Mode `count_up` — Migraine Molly
A counter that grows: "Last dose 1h 47m ago." There is no upper
bound the timer is racing toward — the count-up is informational so
the user can answer questions like "how long since I took my migraine
medication, can I take Tylenol yet?"

The interaction-aware blocking on conflicting medications (UC-4.3) is
what *uses* this counter, but the timer itself doesn't know about
interactions. It just answers "how long ago?"

### Mode `count_down` — Headache Harry
A counter that shrinks toward zero: "Next dose allowed in 47 minutes."
The medication has a `min_interval_minutes`. When zero is reached,
the "taken" button becomes available. Until then it's blocked,
server-side (UC-4.4).

Visually this is the most rewarding mode — the counter ticks down,
and zero means "you can act now."

### Mode `multi_sub_dose` — Billy Bat
The hardest mode. A medication has a *window* (e.g., 6 hours), inside
which a fixed number of sub-doses (e.g., 3) can be taken. The user
wants to spread them evenly to avoid pain valleys, but the only hard
rule is the window total.

Two visual options were considered:

- **One bar split into N segments**, each segment shading in as the
  user takes that sub-dose. This is compact but conflates "time
  elapsed" with "doses taken" — they're different axes.
- **N stacked bars**, one per sub-dose, each showing time-since-that
  -sub-dose. This has more visual real estate but the axes line up.

Working assumption: **N stacked bars**, with a parent bar showing the
overall window. Revisit when 5c lands.

## What ties them together

All four modes are queries against the same underlying data:
`medications.timer_preference`, `medications.min_interval_minutes`,
`medications.window_duration_minutes`, and the `doses` history. The
state machine is a pure function of those inputs plus `now`, per
ADR-0004.

The UI choice (a number, a bar, three bars) is presentation — it
should not require new server-side concepts. If a future mode needs
data the schema doesn't carry, that's a schema change first, design
change second.

## Timer meds on the Today screen (UX-enhancements)

`/today` shows scheduled slots **plus** unscheduled timer meds while
their timer is *running*, so the user sees the whole picture on one
screen. "Running" is `domain.timers.is_timer_active(state)`:

- `count_down` — counting toward the next allowed dose
  (`remaining_seconds > 0`); the row drops off the moment it reaches 0.
- `multi_sub_dose` — the current window is open (it stays even when all
  slots are used, until the window closes by duration; then it drops).
- `count_up` — within **24h** of the last dose (see the resolved
  open question below); past 24h the row drops until the next dose.

These rows carry `schedule_id = null` / `scheduled_time = null`, group
under an "As needed" header, are never muted, and are never gated by
the out-of-schedule confirm.

## Open questions (resolved)

- **Does `count_up` need a soft cap?** — **Yes, 24h.** count_up has no
  intrinsic expiry, so the UI caps the display at "over 24h ago" and
  the Today screen drops an unscheduled count_up row once it passes
  `COUNT_UP_ACTIVE_HORIZON_SECONDS` (86 400) since the last dose.
- For `multi_sub_dose`, what happens when the user *misses* a sub-dose
  and the window expires? Skip silently, mark missed in adherence,
  or surface a warning? *(still open — adherence is a later phase)*
- Mobile haptics on count-down hitting zero — **yes** (implemented in
  Phase 5: a single vibration on the zero crossing while visible).
