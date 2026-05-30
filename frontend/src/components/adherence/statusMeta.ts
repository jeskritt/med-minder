/**
 * Single source of truth for how each adherence DayStatus looks.
 *
 * Every status pairs a Soft-Apothecary semantic color token with a **non-color
 * icon** (SC-005 — never rely on color alone): check / dash / cross / clock.
 * `inactive` carries no status icon (the medication simply wasn't active that
 * day), so its dim, icon-less cell is itself the signal.
 */

import { Check, Clock3, Minus, X } from "lucide-react";
import type { ComponentType } from "react";
import type { DayStatus } from "@/lib/adherence";

export interface StatusMeta {
  /** Human label for tooltips, aria-labels, and the legend. */
  label: string;
  /** Non-color glyph; `null` for inactive (no status). */
  Icon: ComponentType<{ className?: string }> | null;
  /** Calendar tile classes (tinted fill + ring, token-driven). */
  tile: string;
  /** Solid swatch for the legend and trend segments. */
  swatch: string;
}

export const STATUS_META: Record<DayStatus, StatusMeta> = {
  taken: {
    label: "All taken",
    Icon: Check,
    tile: "bg-success/15 text-success ring-1 ring-inset ring-success/30",
    swatch: "bg-success",
  },
  partial: {
    label: "Partially taken",
    Icon: Minus,
    tile: "bg-warning/20 text-warning-foreground ring-1 ring-inset ring-warning/45",
    swatch: "bg-warning",
  },
  missed: {
    label: "Missed",
    Icon: X,
    tile: "bg-destructive/12 text-destructive ring-1 ring-inset ring-destructive/30",
    swatch: "bg-destructive",
  },
  future: {
    label: "Not yet due",
    Icon: Clock3,
    tile: "bg-muted/60 text-muted-foreground ring-1 ring-inset ring-border",
    swatch: "bg-muted-foreground/35",
  },
  inactive: {
    label: "Not scheduled",
    Icon: null,
    tile: "text-muted-foreground/35",
    swatch: "bg-transparent",
  },
};

/** Statuses shown in the calendar legend (inactive omitted — it's the absence). */
export const LEGEND_ORDER: DayStatus[] = [
  "taken",
  "partial",
  "missed",
  "future",
];
