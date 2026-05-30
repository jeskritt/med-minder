/**
 * Month calendar of per-day adherence (US1).
 *
 * Each day is a rounded tile carrying both a semantic color tint and a
 * non-color icon (check / dash / cross / clock), with an accessible label and
 * a hover tooltip giving the exact taken-of-expected count. Tiles fade in with
 * a gentle left-to-right stagger when the month changes — calm, not flashy.
 */

import { useMemo } from "react";
import type { DayAdherence } from "@/lib/adherence";
import { isoDate, mondayFirstColumn } from "@/lib/adherence";
import { STATUS_META } from "./statusMeta";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export interface AdherenceCalendarProps {
  days: DayAdherence[];
  monthAnchor: Date;
}

function tooltipFor(day: DayAdherence): string {
  const meta = STATUS_META[day.status];
  if (day.expected > 0) {
    return `${meta.label} — ${day.taken} of ${day.expected} taken`;
  }
  return meta.label;
}

export function AdherenceCalendar({
  days,
  monthAnchor,
}: AdherenceCalendarProps) {
  const byDate = useMemo(() => {
    const map = new Map<string, DayAdherence>();
    for (const d of days) map.set(d.date, d);
    return map;
  }, [days]);

  const year = monthAnchor.getFullYear();
  const month = monthAnchor.getMonth();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const leadingBlanks = mondayFirstColumn(new Date(year, month, 1));

  return (
    <div>
      <div
        className="mb-2 grid grid-cols-7 gap-1.5 text-center text-[0.65rem] font-semibold uppercase tracking-wide text-muted-foreground/70"
        aria-hidden="true"
      >
        {WEEKDAYS.map((w) => (
          <div key={w}>{w}</div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1.5" role="grid">
        {Array.from({ length: leadingBlanks }).map((_, i) => (
          <div key={`blank-${i}`} aria-hidden="true" />
        ))}

        {Array.from({ length: daysInMonth }).map((_, i) => {
          const dayNum = i + 1;
          const dateStr = isoDate(new Date(year, month, dayNum));
          const day = byDate.get(dateStr);
          const status = day?.status ?? "inactive";
          const meta = STATUS_META[status];
          const Icon = meta.Icon;
          const label = day
            ? `${dateStr}: ${tooltipFor(day)}`
            : `${dateStr}: no data`;

          return (
            <div
              key={dateStr}
              role="gridcell"
              data-status={status}
              title={day ? tooltipFor(day) : undefined}
              aria-label={label}
              className={`animate-in fade-in zoom-in-95 relative flex aspect-square flex-col items-center justify-center rounded-xl text-xs transition-transform duration-200 hover:scale-[1.06] ${meta.tile}`}
              style={{
                animationDelay: `${Math.min(i * 12, 360)}ms`,
                animationFillMode: "both",
              }}
            >
              <span className="absolute left-1.5 top-1 text-[0.6rem] font-medium tabular-nums opacity-70">
                {dayNum}
              </span>
              {Icon && <Icon className="size-3.5" aria-hidden="true" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
