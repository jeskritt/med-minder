import { useState } from "react";
import type { components } from "@/api/v1";

type TodayItem = components["schemas"]["TodayItem"];

export type DoseProgressColor = "green" | "amber" | "red" | "neutral";

const COLOR_CLASS: Record<DoseProgressColor, string> = {
  green: "bg-success",
  amber: "bg-warning",
  red: "bg-destructive",
  neutral: "bg-muted-foreground/30",
};

const LATE_AFTER_MS = 60 * 60 * 1000; // 1 hour (Lenient threshold)
const WARN_HORIZON_MS = 2 * 60 * 60 * 1000; // 2 hours

export interface DoseProgressBarProps {
  item: TodayItem;
  /** Test/seam — defaults to `Date.now()`. */
  now?: number;
}

/**
 * Per-row color-coded progress bar for /today.
 *
 * Color is purely visual (lenient threshold semantics — never gates the
 * take button):
 * - green: taken today
 * - red: an active overdose / interaction guard would block a take
 *   (count_down min-interval not elapsed, multi_sub_dose window full,
 *   or an active interaction-cooldown conflict)
 * - amber: scheduled today, > 1 h past scheduled time, not taken
 * - neutral: anything else
 *
 * Value defaults to `clamp(elapsed_since_scheduled / 2h, 0, 1)` so it
 * grows from empty at the scheduled moment toward full at the warning
 * horizon. Timer modes don't override this — the per-mode component
 * (CountDownButton / MultiSubDoseCard) carries its own native readout.
 */
export function DoseProgressBar({ item, now }: DoseProgressBarProps) {
  // `Date.now()` is impure; lazy-init via useState satisfies React's
  // purity rule and freezes "now" for the lifetime of this row. Callers
  // re-render the whole today list on dose mutations, so we get fresh
  // bars then; no per-second tick is needed (lenient threshold = 1h).
  const [defaultNow] = useState(() => Date.now());
  const resolved = now ?? defaultNow;
  const color = pickColor(item, resolved);
  const value = pickValue(item, resolved);
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={1}
      aria-valuenow={value}
      data-color={color}
      className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted"
    >
      <div
        className={`h-full rounded-full transition-[width] duration-500 ${COLOR_CLASS[color]}`}
        style={{ width: `${Math.round(value * 100)}%` }}
      />
    </div>
  );
}

function isOverdoseRed(item: TodayItem): boolean {
  if (item.interaction_state) return true;
  const cd = item.timer_state?.count_down;
  if (cd && cd.remaining_seconds > 0) return true;
  const msd = item.timer_state?.multi_sub_dose;
  if (msd && msd.slots_remaining === 0) {
    return true;
  }
  return false;
}

function scheduledMsToday(scheduledTime: string, now: number): number {
  const ref = new Date(now);
  const [hh, mm] = scheduledTime.split(":");
  ref.setHours(Number(hh), Number(mm), 0, 0);
  return ref.getTime();
}

function pickColor(item: TodayItem, now: number): DoseProgressColor {
  if (item.dose !== null) return "green";
  if (isOverdoseRed(item)) return "red";
  // Unscheduled (PRN) rows have no day-of-week / scheduled-time horizon.
  if (!item.scheduled_today || item.scheduled_time === null) return "neutral";
  const scheduledAt = scheduledMsToday(item.scheduled_time, now);
  if (now - scheduledAt > LATE_AFTER_MS) return "amber";
  return "neutral";
}

function pickValue(item: TodayItem, now: number): number {
  if (item.dose !== null) return 1;
  // PRN rows have no scheduled horizon to fill against — render empty;
  // the per-mode control (countdown / window) carries the real readout.
  if (item.scheduled_time === null) return 0;
  const scheduledAt = scheduledMsToday(item.scheduled_time, now);
  const elapsed = now - scheduledAt;
  if (elapsed <= 0) return 0;
  return Math.min(1, elapsed / WARN_HORIZON_MS);
}
