import type { components } from "@/api/v1";
import type { MedicationFormValues } from "./medicationFormSchema";

type MedicationOut = components["schemas"]["MedicationOut"];

/**
 * Map a server `MedicationOut` to the form's string-keyed values.
 *
 * Lives in its own module (not `MedicationForm.tsx`) so the component
 * file exports only a component — keeps it Fast-Refresh clean
 * (react-refresh/only-export-components). Existing interaction rules
 * are injected separately by the edit route from its rules query.
 */
export function defaultsFromMedication(
  med: MedicationOut,
): MedicationFormValues {
  return {
    name: med.name,
    quantity_per_dose: String(med.quantity_per_dose),
    unit: med.unit,
    times_per_day: String(med.times_per_day),
    start_date: med.start_date ?? "",
    end_date: med.end_date ?? "",
    untracked: med.total_doses === null,
    total_doses:
      med.total_doses === null || med.total_doses === undefined
        ? ""
        : String(med.total_doses),
    refill_count:
      med.refill_count === null || med.refill_count === undefined
        ? ""
        : String(med.refill_count),
    refill_threshold:
      med.refill_threshold === null || med.refill_threshold === undefined
        ? ""
        : String(med.refill_threshold),
    timer_preference: med.timer_preference,
    min_interval_minutes:
      med.min_interval_minutes === null ||
      med.min_interval_minutes === undefined
        ? ""
        : String(med.min_interval_minutes),
    window_duration_minutes:
      med.window_duration_minutes === null ||
      med.window_duration_minutes === undefined
        ? ""
        : String(med.window_duration_minutes),
    schedules: med.schedules.map((s) => ({
      time_of_day: s.time_of_day.slice(0, 5),
    })),
    conflicts: [],
  };
}
