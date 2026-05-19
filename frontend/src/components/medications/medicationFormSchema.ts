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

export const medicationFormSchema = z
  .object({
    name: z.string().trim().min(1, "Name is required").max(200),
    quantity_per_dose: z
      .string()
      .trim()
      .refine((v) => v.length > 0, "Dosage is required")
      .refine(
        (v) => Number.isFinite(Number(v)) && Number(v) > 0,
        "Dosage must be a positive number",
      ),
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
    min_interval_minutes: positiveIntString,
    window_duration_minutes: positiveIntString,
    schedules: z.array(
      z.object({
        time_of_day: z.string().min(1, "Time is required"),
      }),
    ),
    conflicts: z.array(
      z.object({
        other_medication_id: z.string().min(1, "Pick a medication"),
        cooldown_minutes: z
          .string()
          .trim()
          .refine(
            (v) => /^[0-9]+$/.test(v) && Number(v) > 0,
            "Cooldown must be a whole number greater than zero",
          ),
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
      v.timer_preference !== "count_down" ||
      (/^[0-9]+$/.test(v.min_interval_minutes) &&
        Number(v.min_interval_minutes) > 0),
    {
      message: "count_down requires a minimum interval in minutes",
      path: ["min_interval_minutes"],
    },
  )
  .refine(
    (v) =>
      v.timer_preference !== "multi_sub_dose" ||
      (/^[0-9]+$/.test(v.window_duration_minutes) &&
        Number(v.window_duration_minutes) > 0),
    {
      message: "multi_sub_dose requires a window duration in minutes",
      path: ["window_duration_minutes"],
    },
  )
  .refine(
    (v) =>
      v.timer_preference !== "multi_sub_dose" ||
      (/^[0-9]+$/.test(v.times_per_day) && Number(v.times_per_day) >= 1),
    {
      message: "multi_sub_dose requires at least 1 time per day",
      path: ["times_per_day"],
    },
  );

export type MedicationFormValues = z.infer<typeof medicationFormSchema>;
