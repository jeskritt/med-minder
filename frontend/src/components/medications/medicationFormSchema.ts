import { z } from "zod";

const optionalIntString = z
  .string()
  .trim()
  .refine(
    (v) => v === "" || /^[0-9]+$/.test(v),
    "Must be a non-negative whole number",
  );

const positiveIntString = z
  .string()
  .trim()
  .refine(
    (v) => v === "" || (/^[0-9]+$/.test(v) && Number(v) > 0),
    "Must be a whole number greater than zero",
  );

const positiveDecimalString = z
  .string()
  .trim()
  .refine(
    (v) => v === "" || (Number.isFinite(Number(v)) && Number(v) > 0),
    "Must be a number greater than zero",
  );

const DURATION_UNIT = z.enum(["min", "hour", "day"]);
export type DurationUnit = z.infer<typeof DURATION_UNIT>;

export const medicationFormSchema = z
  .object({
    name: z.string().trim().min(1, "Name is required").max(200),
    // Quantity per dose: stays as a string for non-pill meds. When
    // `pill_based` is true the form derives it from pill_strength *
    // pills_per_dose and this field is ignored on submit.
    quantity_per_dose: z.string().trim(),
    unit: z.string().trim().min(1, "Unit is required").max(50),
    times_per_day: z
      .string()
      .trim()
      .refine((v) => /^[0-9]+$/.test(v) && Number(v) <= 24, "Enter 0–24"),
    start_date: z.string(),
    end_date: z.string(),
    untracked: z.boolean(),
    total_doses: optionalIntString,
    refill_count: optionalIntString,
    refill_threshold: optionalIntString,
    timer_preference: z.enum([
      "none",
      "count_up",
      "count_down",
      "multi_sub_dose",
    ]),
    // Duration fields split into value + unit pair for friendlier input;
    // converted to minutes on submit. Stored as positive int strings.
    min_interval_value: positiveIntString,
    min_interval_unit: DURATION_UNIT,
    window_duration_value: positiveIntString,
    window_duration_unit: DURATION_UNIT,
    // UX enhancements: pill-based dosage.
    pill_based: z.boolean(),
    pill_strength: positiveDecimalString,
    pills_per_dose: positiveIntString,
    // UX enhancements: multi_sub_dose per-day cap.
    max_doses_per_day: optionalIntString,
    // UX enhancements: schedules are shared user-level resources;
    // the form sends existing ids rather than HH:MM strings.
    // Ids come from the server (`/api/v1/schedules`); leave strict
    // UUID-format validation to the backend.
    selected_schedule_ids: z.array(z.string().min(1)),
    conflicts: z.array(
      z.object({
        other_medication_id: z.string().min(1, "Pick a medication"),
        // Cooldown as a value + unit pair (like min_interval / window_duration),
        // converted to minutes on submit. Value is a required positive int.
        cooldown_value: z
          .string()
          .trim()
          .refine(
            (v) => /^[0-9]+$/.test(v) && Number(v) > 0,
            "Cooldown must be a whole number greater than zero",
          ),
        cooldown_unit: DURATION_UNIT,
      }),
    ),
  })
  .refine(
    (v) => {
      const ids = v.conflicts.map((c) => c.other_medication_id);
      return new Set(ids).size === ids.length;
    },
    {
      message: "Each medication can only be listed once",
      path: ["conflicts"],
    },
  )
  .refine(
    (v) =>
      v.start_date === "" || v.end_date === "" || v.end_date >= v.start_date,
    {
      message: "End date must be on or after start date",
      path: ["end_date"],
    },
  )
  .refine(
    (v) =>
      v.untracked ||
      v.total_doses === "" ||
      (/^[0-9]+$/.test(v.total_doses) && Number(v.total_doses) > 0),
    {
      message: "Total doses must be > 0, or check Untracked / As Needed",
      path: ["total_doses"],
    },
  )
  .refine(
    (v) =>
      v.pill_based ||
      (Number.isFinite(Number(v.quantity_per_dose)) &&
        Number(v.quantity_per_dose) > 0),
    {
      message: "Dosage must be a positive number",
      path: ["quantity_per_dose"],
    },
  )
  .refine((v) => !v.pill_based || Number(v.pill_strength) > 0, {
    message: "Pill strength must be greater than zero",
    path: ["pill_strength"],
  })
  .refine(
    (v) =>
      !v.pill_based ||
      (/^[0-9]+$/.test(v.pills_per_dose) && Number(v.pills_per_dose) > 0),
    {
      message: "Pills per dose must be a whole number greater than zero",
      path: ["pills_per_dose"],
    },
  )
  .refine(
    (v) =>
      v.timer_preference !== "count_down" ||
      (/^[0-9]+$/.test(v.min_interval_value) &&
        Number(v.min_interval_value) > 0),
    {
      message: "count_down requires a minimum interval",
      path: ["min_interval_value"],
    },
  )
  .refine(
    (v) =>
      v.timer_preference !== "multi_sub_dose" ||
      (/^[0-9]+$/.test(v.window_duration_value) &&
        Number(v.window_duration_value) > 0),
    {
      message: "multi_sub_dose requires a window duration",
      path: ["window_duration_value"],
    },
  )
  .refine(
    (v) =>
      v.timer_preference !== "multi_sub_dose" ||
      (/^[0-9]+$/.test(v.times_per_day) && Number(v.times_per_day) >= 1),
    {
      message: "multi_sub_dose requires at least 1 time per window",
      path: ["times_per_day"],
    },
  )
  .refine(
    (v) =>
      v.timer_preference !== "multi_sub_dose" ||
      v.max_doses_per_day === "" ||
      Number(v.max_doses_per_day) >= Number(v.times_per_day || "0"),
    {
      message: "Max doses per day must be ≥ times per window",
      path: ["max_doses_per_day"],
    },
  );

export type MedicationFormValues = z.infer<typeof medicationFormSchema>;

/** Convert a (value, unit) pair to minutes. Returns null when value is "". */
export function durationToMinutes(
  value: string,
  unit: DurationUnit,
): number | null {
  if (value === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  const mult = unit === "day" ? 1440 : unit === "hour" ? 60 : 1;
  return n * mult;
}

/** Split a minutes value into (value, unit) using the largest exact divisor. */
export function minutesToDuration(minutes: number | null | undefined): {
  value: string;
  unit: DurationUnit;
} {
  if (minutes === null || minutes === undefined) {
    return { value: "", unit: "min" };
  }
  if (minutes % 1440 === 0)
    return { value: String(minutes / 1440), unit: "day" };
  if (minutes % 60 === 0) return { value: String(minutes / 60), unit: "hour" };
  return { value: String(minutes), unit: "min" };
}
