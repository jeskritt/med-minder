/**
 * Stacked-bar trend of per-day adherence over a window (US3).
 *
 * One bar per day; height is scaled to the day's expected-dose count, and each
 * bar stacks taken (success) over missed/pending (token-driven). Renders from
 * the same per-day payload as the calendar (research D7) — no extra request.
 */

import { useMemo } from "react";
import type { DayAdherence } from "@/lib/adherence";

export interface AdherenceTrendProps {
  days: DayAdherence[];
}

function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${Number(m)}/${Number(d)}`;
}

export function AdherenceTrend({ days }: AdherenceTrendProps) {
  const maxExpected = useMemo(
    () => Math.max(1, ...days.map((d) => d.expected)),
    [days],
  );

  return (
    <div
      className="flex items-end gap-1 overflow-x-auto pb-1"
      style={{ height: "9rem" }}
      role="img"
      aria-label="Daily adherence trend"
    >
      {days.map((day, i) => {
        const taken = day.taken;
        const untaken = Math.max(0, day.expected - day.taken);
        const isMissed = day.status === "missed" || day.status === "partial";
        const takenPct = (taken / maxExpected) * 100;
        const untakenPct = (untaken / maxExpected) * 100;
        const label =
          day.expected > 0
            ? `${shortDate(day.date)}: ${taken} of ${day.expected} taken`
            : `${shortDate(day.date)}: not scheduled`;

        return (
          <div
            key={day.date}
            className="flex min-w-[0.5rem] flex-1 flex-col justify-end"
            title={label}
            aria-label={label}
            data-status={day.status}
          >
            <div className="flex h-full flex-col justify-end gap-0.5">
              {/* Untaken portion: clay-red when missed/partial, faint when pending. */}
              {untaken > 0 && (
                <div
                  className={`animate-in fade-in slide-in-from-bottom-1 w-full rounded-sm ${
                    isMissed ? "bg-destructive/70" : "bg-muted-foreground/25"
                  }`}
                  style={{
                    height: `${untakenPct}%`,
                    animationDelay: `${Math.min(i * 14, 320)}ms`,
                    animationFillMode: "both",
                  }}
                />
              )}
              {taken > 0 && (
                <div
                  className="animate-in fade-in slide-in-from-bottom-1 w-full rounded-sm bg-success"
                  style={{
                    height: `${takenPct}%`,
                    animationDelay: `${Math.min(i * 14, 320)}ms`,
                    animationFillMode: "both",
                  }}
                />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
