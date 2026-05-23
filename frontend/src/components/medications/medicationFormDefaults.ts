import type { components } from "@/api/v1";
import { formatQuantity } from "@/lib/format";
import {
  minutesToDuration,
  type MedicationFormValues,
} from "./medicationFormSchema";

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
  const minInterval = minutesToDuration(med.min_interval_minutes ?? null);
  const windowDuration = minutesToDuration(med.window_duration_minutes ?? null);
  const pillBased =
    med.pill_strength !== null &&
    med.pill_strength !== undefined &&
    med.pills_per_dose !== null &&
    med.pills_per_dose !== undefined;
  return {
    name: med.name,
    quantity_per_dose: formatQuantity(med.quantity_per_dose),
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
    min_interval_value: minInterval.value,
    min_interval_unit: minInterval.unit,
    window_duration_value: windowDuration.value,
    window_duration_unit: windowDuration.unit,
    pill_based: pillBased,
    pill_strength:
      med.pill_strength === null || med.pill_strength === undefined
        ? ""
        : formatQuantity(med.pill_strength),
    pills_per_dose:
      med.pills_per_dose === null || med.pills_per_dose === undefined
        ? ""
        : String(med.pills_per_dose),
    max_doses_per_day:
      med.max_doses_per_day === null || med.max_doses_per_day === undefined
        ? ""
        : String(med.max_doses_per_day),
    selected_schedule_ids: med.schedules.map((s) => s.id),
    conflicts: [],
  };
}
