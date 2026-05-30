/**
 * Pure helpers for the adherence views (Phase 9).
 *
 * Date helpers build the `from`/`to` (inclusive, local YYYY-MM-DD) window the
 * adherence endpoint expects, and `downloadDoseHistoryCsv` triggers a browser
 * download of the CSV export. Status presentation (color token + non-color
 * icon) lives in `components/adherence/statusMeta`.
 */

import type { components } from "@/api/v1";

export type DayAdherence = components["schemas"]["DayAdherenceOut"];
export type DayStatus = DayAdherence["status"];
export type MedicationAdherence =
  components["schemas"]["MedicationAdherenceOut"];
export type CourseProgress = components["schemas"]["CourseProgressOut"];

export interface DateWindow {
  from: string;
  to: string;
}

/** Local YYYY-MM-DD for a Date (no UTC shift). */
export function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** First/last day of the month containing `anchor`, as a window. */
export function monthWindow(anchor: Date): DateWindow {
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
  return { from: isoDate(first), to: isoDate(last) };
}

/** The last `days` days ending today (inclusive), as a window. */
export function trailingWindow(
  days: number,
  today: Date = new Date(),
): DateWindow {
  const start = new Date(today);
  start.setDate(start.getDate() - (days - 1));
  return { from: isoDate(start), to: isoDate(today) };
}

/** Add `delta` months to a month anchor (first-of-month). */
export function addMonths(anchor: Date, delta: number): Date {
  return new Date(anchor.getFullYear(), anchor.getMonth() + delta, 1);
}

/** Monday-first column index (0–6) for a Date. */
export function mondayFirstColumn(d: Date): number {
  return (d.getDay() + 6) % 7;
}

/**
 * Fetch the CSV export and trigger a browser download. Uses a raw `fetch`
 * (not the typed client) because the body is a CSV blob, not JSON.
 *
 * `from`/`to` (inclusive local YYYY-MM-DD) optionally bound the export;
 * omit both for the full history.
 */
export async function downloadDoseHistoryCsv(opts?: {
  from?: string;
  to?: string;
}): Promise<void> {
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  const params = new URLSearchParams();
  if (opts?.from) params.set("from", opts.from);
  if (opts?.to) params.set("to", opts.to);
  const query = params.toString();
  const resp = await fetch(
    `${base}/api/v1/adherence/export.csv${query ? `?${query}` : ""}`,
    { credentials: "include" },
  );
  if (!resp.ok) {
    throw new Error("Could not export dose history.");
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "medminder-doses.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
