import { Link } from "@tanstack/react-router";
import type { components } from "@/api/v1";

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
      <p className="mt-4 text-gray-600">
        No medications yet.{" "}
        <Link to="/medications/new" className="text-blue-600 underline">
          Add your first one
        </Link>
        .
      </p>
    );
  }

  return (
    <ul className="mt-4 divide-y rounded border print:border-0">
      {items.map((med) => (
        <li
          key={med.id}
          className="flex items-start justify-between gap-4 p-3 print:p-1"
        >
          <div>
            <div className="font-medium">
              {med.name}{" "}
              <span className="text-sm text-gray-600">
                ({med.quantity_per_dose} {med.unit})
              </span>
            </div>
            <div className="text-sm text-gray-700">
              {med.times_per_day}× daily — {formatTimes(med)}
            </div>
            {(med.refill_count !== null || med.refill_threshold !== null) && (
              <div className="text-xs text-gray-600">
                Refill: {med.refill_count ?? "—"} on hand
                {med.refill_threshold !== null
                  ? `, warn at ${med.refill_threshold}`
                  : ""}
              </div>
            )}
          </div>
          <div className="flex shrink-0 gap-2 print:hidden">
            <Link
              to="/medications/$id/edit"
              params={{ id: med.id }}
              className="rounded border px-2 py-1 text-sm hover:bg-gray-50"
            >
              Edit
            </Link>
            {onDelete && (
              <button
                type="button"
                onClick={() => onDelete(med.id)}
                disabled={deletingId === med.id}
                className="rounded border border-red-300 px-2 py-1 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
              >
                {deletingId === med.id ? "Deleting…" : "Delete"}
              </button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
