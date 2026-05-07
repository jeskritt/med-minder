import { useFieldArray, type Control, type FieldErrors } from "react-hook-form";
import type { MedicationFormValues } from "./medicationFormSchema";

interface ScheduleInputProps {
  control: Control<MedicationFormValues>;
  errors: FieldErrors<MedicationFormValues>;
  timesPerDay: number;
}

export function ScheduleInput({
  control,
  errors,
  timesPerDay,
}: ScheduleInputProps) {
  const { fields, append, remove } = useFieldArray({
    control,
    name: "schedules",
  });

  const mismatch =
    Number.isFinite(timesPerDay) && timesPerDay !== fields.length;

  return (
    <fieldset className="mt-4 rounded border p-3">
      <legend className="px-1 text-sm font-medium">Schedules</legend>
      <p className="text-xs text-gray-600">
        One entry per scheduled dose (local wall-clock time).
      </p>

      {fields.length === 0 && (
        <p className="mt-2 text-sm italic text-gray-500">
          No schedules yet. Add one below.
        </p>
      )}

      <ul className="mt-2 space-y-2">
        {fields.map((field, index) => (
          <li key={field.id} className="flex items-center gap-2">
            <input
              type="time"
              aria-label={`Schedule ${index + 1} time`}
              className="rounded border px-2 py-1"
              {...control.register(`schedules.${index}.time_of_day` as const)}
            />
            <button
              type="button"
              onClick={() => remove(index)}
              className="rounded border px-2 py-1 text-sm hover:bg-gray-50"
              aria-label={`Remove schedule ${index + 1}`}
            >
              Remove
            </button>
            {errors.schedules?.[index]?.time_of_day && (
              <span role="alert" className="text-sm text-red-600">
                {errors.schedules[index]?.time_of_day?.message}
              </span>
            )}
          </li>
        ))}
      </ul>

      <button
        type="button"
        onClick={() => append({ time_of_day: "" })}
        className="mt-3 rounded border px-3 py-1 text-sm hover:bg-gray-50"
      >
        Add schedule
      </button>

      {mismatch && (
        <p
          role="alert"
          className="mt-3 rounded bg-yellow-50 px-2 py-1 text-sm text-yellow-800"
        >
          Heads up: you set <strong>{timesPerDay}</strong> times per day but
          have <strong>{fields.length}</strong> schedule
          {fields.length === 1 ? "" : "s"} attached.
        </p>
      )}
    </fieldset>
  );
}
