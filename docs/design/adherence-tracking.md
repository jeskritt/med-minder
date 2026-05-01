# Design — Long-term adherence views

This is exploratory design thinking, not a binding spec. The
authoritative behavior lives in `docs/user_stories.md` UC-6 and the
implementation in Phase 9.

## The user question

"Did I take my blood pressure medication yesterday? Last week?"

Granny, Diabetic Dan, and any user with a long-running prescription
asks variants of this question. They don't want a log of timestamps.
They want a glance at a calendar that tells them *yes* or *no* for
each day, and a way to spot a streak of misses.

## Visual options

### Calendar grid (preferred for "did I take it yesterday?")
Month view, one cell per day, color-coded:

- **green** — all scheduled doses taken
- **yellow** — partial (some scheduled doses taken, others missed)
- **red** — fully missed
- **gray** — scheduled in the future
- **white** — medication wasn't active that day (start_date / end_date)

This answers the per-day question instantly and shows weekly patterns
("I always miss Saturdays").

### Stacked bar (preferred for "how am I doing this month?")
One bar per day across a configurable window (week / month). Bar
height is the number of scheduled doses; segments are colored
taken / partial / missed.

This is denser than the calendar but better at showing trends over
time.

Working assumption: **both views, switchable.** They answer different
questions and the implementation cost of the second is low if the
first is well-modeled.

## Color choices

Color alone is not accessible (UC-7 implies WCAG-conscious design,
Phase 10 enforces). Each cell needs a non-color signal:

- A check / dash / cross icon in addition to the color.
- A tooltip with the exact dose count and times.

The Tailwind palette already gives us accessible green/yellow/red
defaults; verify contrast in Phase 10.

## What "missed" means

A scheduled dose is "missed" if no `doses` row exists for it within a
tolerance window after the scheduled time (working assumption: 4
hours). The tolerance is per-medication configurable in v2 if needed;
v1 can hardcode.

A PRN medication (timer mode `count_down` or `none` with no schedule)
has no concept of "missed" — only "taken N times today." The
calendar should still color these green/gray rather than red, since
"not taken today" doesn't mean the user failed.

## Export

CSV export per UC-6.3. Schema:

```
medication_name, taken_at, quantity, unit, schedule_label, soft_deleted
```

Soft-deleted medications are still included so that a six-month-old
export remains coherent if the user later cleans up their list.

## Open questions

- Should adherence counts include un-taken (compensated) doses? The
  honest answer is "no, they were corrected" — but corrections are
  rare and worth noting in the export.
- Time zone for the calendar: user's TZ at the time of the dose, or
  user's *current* TZ? Working assumption: user's *current* TZ
  (consistent with the rest of the app).

These get resolved in the Phase 9 PRs.
