/**
 * Adherence section for the medication detail page (US1 + US2 + US3).
 *
 * Owns the calendar ⇄ trend toggle and the visible window, fetches one payload
 * (research D7), and renders the percentage stat, the active view, the legend,
 * and course progress. Soft-Apothecary throughout: semantic tokens, mm-* pills,
 * calm motion.
 */

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMedicationAdherence } from "@/hooks/useMedicationAdherence";
import {
  addMonths,
  monthWindow,
  trailingWindow,
  type DateWindow,
} from "@/lib/adherence";
import { AdherenceCalendar } from "./AdherenceCalendar";
import { AdherenceTrend } from "./AdherenceTrend";
import { CourseProgress } from "./CourseProgress";
import { LEGEND_ORDER, STATUS_META } from "./statusMeta";

type ViewMode = "calendar" | "trend";
type TrendWindow = 7 | 30;

export interface AdherenceViewProps {
  medicationId: string;
}

export function AdherenceView({ medicationId }: AdherenceViewProps) {
  const [mode, setMode] = useState<ViewMode>("calendar");
  const [monthAnchor, setMonthAnchor] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [trendDays, setTrendDays] = useState<TrendWindow>(7);

  const window: DateWindow = useMemo(
    () =>
      mode === "calendar"
        ? monthWindow(monthAnchor)
        : trailingWindow(trendDays),
    [mode, monthAnchor, trendDays],
  );

  const query = useMedicationAdherence(medicationId, window);

  const monthLabel = monthAnchor.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
  const pct = query.data?.adherence_pct ?? null;
  const windowLabel =
    mode === "calendar"
      ? monthLabel
      : trendDays === 7
        ? "last 7 days"
        : "last 30 days";

  return (
    <section className="mm-card p-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-foreground">
            Adherence
          </h2>
          {pct !== null ? (
            <p className="text-sm text-muted-foreground">
              <span className="text-xl font-bold tabular-nums text-foreground">
                {pct}%
              </span>{" "}
              taken · {windowLabel}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              No scheduled doses to score · {windowLabel}
            </p>
          )}
        </div>

        <div
          className="inline-flex rounded-full bg-muted p-0.5"
          role="tablist"
          aria-label="Adherence view"
        >
          {(["calendar", "trend"] as ViewMode[]).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={`mm-btn mm-btn-sm capitalize ${
                mode === m
                  ? "bg-card text-foreground shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </header>

      {/* Window controls */}
      <div className="mt-4 flex items-center justify-between">
        {mode === "calendar" ? (
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Previous month"
              onClick={() => setMonthAnchor((a) => addMonths(a, -1))}
              className="mm-btn mm-btn-ghost mm-btn-sm"
            >
              <ChevronLeft />
            </button>
            <span className="min-w-36 text-center text-sm font-medium text-foreground">
              {monthLabel}
            </span>
            <button
              type="button"
              aria-label="Next month"
              onClick={() => setMonthAnchor((a) => addMonths(a, 1))}
              className="mm-btn mm-btn-ghost mm-btn-sm"
            >
              <ChevronRight />
            </button>
          </div>
        ) : (
          <div className="inline-flex rounded-full bg-muted p-0.5">
            {([7, 30] as TrendWindow[]).map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setTrendDays(d)}
                aria-pressed={trendDays === d}
                className={`mm-btn mm-btn-sm ${
                  trendDays === d
                    ? "bg-card text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {d === 7 ? "Week" : "Month"}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 min-h-[12rem]">
        {query.isLoading && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Loading…
          </p>
        )}
        {query.isError && (
          <p role="alert" className="py-8 text-center text-sm text-destructive">
            Could not load adherence.
          </p>
        )}
        {query.isSuccess &&
          (mode === "calendar" ? (
            <AdherenceCalendar
              days={query.data.days}
              monthAnchor={monthAnchor}
            />
          ) : (
            <AdherenceTrend days={query.data.days} />
          ))}
      </div>

      {/* Legend — color + icon, so the coding is readable without color alone */}
      {mode === "calendar" && (
        <ul className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-border pt-3 text-xs text-muted-foreground">
          {LEGEND_ORDER.map((status) => {
            const meta = STATUS_META[status];
            const Icon = meta.Icon;
            return (
              <li key={status} className="flex items-center gap-1.5">
                <span
                  className={`flex size-4 items-center justify-center rounded ${meta.tile}`}
                >
                  {Icon && <Icon className="size-3" aria-hidden="true" />}
                </span>
                {meta.label}
              </li>
            );
          })}
        </ul>
      )}

      {query.isSuccess && query.data.course && (
        <div className="mt-4">
          <CourseProgress course={query.data.course} />
        </div>
      )}
    </section>
  );
}
