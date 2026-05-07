import { z } from "zod";

const optionalIntString = z
  .string()
  .trim()
  .refine(
    (v) => v === "" || /^[0-9]+$/.test(v),
    "Must be a non-negative whole number",
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
    schedules: z.array(
      z.object({
        time_of_day: z.string().min(1, "Time is required"),
      }),
    ),
  })
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
  );

export type MedicationFormValues = z.infer<typeof medicationFormSchema>;
