import { Link } from "@tanstack/react-router";
import { BarChart2, Pencil, PackageOpen, Trash2 } from "lucide-react";
import type { components } from "@/api/v1";
import { CountUpDisplay } from "@/components/timers/CountUpDisplay";
import { CountDownButton } from "@/components/timers/CountDownButton";
import { MultiSubDoseCard } from "@/components/timers/MultiSubDoseCard";
import { InteractionIndicator } from "@/components/InteractionIndicator";
import { formatQuantity } from "@/lib/format";

type MedicationOut = components["schemas"]["MedicationOut"];

export interface MedicationListProps {
  items: MedicationOut[];
  onDelete?: (id: string) => void;
  deletingId?: string | null;
}

function formatTimes(med: MedicationOut): string {
  if (med.schedules.length === 0) return "no schedule set";
  return med.schedules.map((s) => s.time_of_day.slice(0, 5)).join(", ");
}

export function MedicationList({
  items,
  onDelete,
  deletingId,
}: MedicationListProps) {
  if (items.length === 0) {
    return (
      <div className="mm-card mt-6 px-6 py-10 text-center print:hidden">
        <p className="font-medium text-foreground">No medications yet</p>
        <p className="mt-1 text-sm text-muted-foreground">
          <Link
            to="/medications/new"
            className="font-medium text-primary hover:underline"
          >
            Add your first one
          </Link>{" "}
          to start tracking doses.
        </p>
      </div>
    );
  }

  return (
    <ul className="mt-5 space-y-3 print:space-y-1">
      {items.map((med) => {
        const lowRefill =
          med.refill_count !== null &&
          med.refill_threshold !== null &&
          med.refill_count <= med.refill_threshold;
        return (
          <li
            key={med.id}
            className="mm-card flex items-start justify-between gap-4 p-4 print:rounded-none print:border-0 print:p-1 print:shadow-none"
          >
            <div className="min-w-0">
              <div className="font-semibold text-foreground">
                <Link
                  to="/medications/$medicationId"
                  params={{ medicationId: med.id }}
                  className="text-primary underline decoration-primary/30 underline-offset-2 hover:decoration-primary"
                >
                  {med.name}
                </Link>{" "}
                <span className="text-sm font-normal text-muted-foreground">
                  {formatQuantity(med.quantity_per_dose)} {med.unit}
                </span>
              </div>
              <div className="text-sm text-muted-foreground">
                {med.timer_state?.mode === "multi_sub_dose"
                  ? `max ${med.times_per_day} at a time`
                  : `${med.times_per_day}× daily`}{" "}
                — {formatTimes(med)}
              </div>
              {med.timer_state?.mode === "count_up" && (
                <div className="mt-0.5 text-sm text-muted-foreground">
                  <CountUpDisplay state={med.timer_state} />
                </div>
              )}
              {med.timer_state?.mode === "count_down" && (
                <div className="mt-2">
                  <CountDownButton
                    state={med.timer_state}
                    medicationId={med.id}
                  />
                </div>
              )}
              {med.timer_state?.mode === "multi_sub_dose" && (
                <div className="mt-2">
                  <MultiSubDoseCard
                    state={med.timer_state}
                    medicationId={med.id}
                  />
                </div>
              )}
              {med.interaction_state && (
                <div className="mt-2">
                  <InteractionIndicator state={med.interaction_state} />
                </div>
              )}
              {(med.refill_count !== null || med.refill_threshold !== null) && (
                <div
                  className={
                    lowRefill
                      ? "mm-chip mt-2 bg-warning/15 text-warning-foreground"
                      : "mt-2 text-xs text-muted-foreground"
                  }
                >
                  {lowRefill && <PackageOpen className="size-3.5" />}
                  Refill: {med.refill_count ?? "—"} on hand
                  {med.refill_threshold !== null
                    ? `, warn at ${med.refill_threshold}`
                    : ""}
                </div>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-1.5 print:hidden">
              <Link
                to="/medications/$medicationId"
                params={{ medicationId: med.id }}
                aria-label={`View adherence for ${med.name}`}
                title="Adherence"
                className="mm-btn mm-btn-secondary size-9 p-0"
              >
                <BarChart2 className="size-4" />
              </Link>
              <Link
                to="/medications/$id/edit"
                params={{ id: med.id }}
                aria-label={`Edit ${med.name}`}
                className="mm-btn mm-btn-secondary size-9 p-0"
              >
                <Pencil className="size-4" />
              </Link>
              {onDelete && (
                <button
                  type="button"
                  onClick={() => onDelete(med.id)}
                  disabled={deletingId === med.id}
                  aria-label={`Delete ${med.name}`}
                  className="mm-btn mm-btn-danger size-9 p-0"
                >
                  <Trash2 className="size-4" />
                </button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
