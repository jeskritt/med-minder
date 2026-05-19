import {
  useForm,
  useFieldArray,
  useWatch,
  type SubmitHandler,
} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { components } from "@/api/v1";
import {
  medicationFormSchema,
  type MedicationFormValues,
} from "./medicationFormSchema";
import { ScheduleInput } from "./ScheduleInput";

type MedicationBody = components["schemas"]["MedicationBody"];

/** One symmetric interaction rule the form wants persisted (US3). */
export interface ConflictInput {
  other_medication_id: string;
  cooldown_minutes: number;
}

export interface MedicationFormProps {
  /** ``"create"`` or ``"edit"`` mode — controls submit button label only. */
  mode: "create" | "edit";
  /** Initial values, e.g. when editing.  Optional. */
  defaultValues?: Partial<MedicationFormValues>;
  /**
   * Other medications the user owns (for the "Conflicts with"
   * selector). MUST exclude the medication being edited.
   */
  availableMedications?: { id: string; name: string }[];
  /** Called with the API-shaped body + interaction rules once valid. */
  onSubmit: (
    body: MedicationBody,
    conflicts: ConflictInput[],
  ) => Promise<void> | void;
  /** Optional server-error message rendered above the submit button. */
  serverError?: string | null;
  /** True while the parent's mutation is in flight. */
  isSubmitting?: boolean;
}

const EMPTY_DEFAULTS: MedicationFormValues = {
  name: "",
  quantity_per_dose: "",
  unit: "",
  times_per_day: "1",
  start_date: "",
  end_date: "",
  untracked: false,
  total_doses: "",
  refill_count: "",
  refill_threshold: "",
  timer_preference: "none",
  min_interval_minutes: "",
  window_duration_minutes: "",
  schedules: [],
  conflicts: [],
};

function toApiBody(values: MedicationFormValues): MedicationBody {
  const intOrNull = (v: string): number | null => (v === "" ? null : Number(v));
  return {
    name: values.name.trim(),
    quantity_per_dose: values.quantity_per_dose,
    unit: values.unit.trim(),
    times_per_day: Number(values.times_per_day),
    start_date: values.start_date === "" ? null : values.start_date,
    end_date: values.end_date === "" ? null : values.end_date,
    total_doses: values.untracked ? null : intOrNull(values.total_doses),
    refill_count: intOrNull(values.refill_count),
    refill_threshold: intOrNull(values.refill_threshold),
    timer_preference: values.timer_preference,
    min_interval_minutes: intOrNull(values.min_interval_minutes),
    window_duration_minutes: intOrNull(values.window_duration_minutes),
    schedules: values.schedules.map((s) => s.time_of_day),
  };
}

export function MedicationForm({
  mode,
  defaultValues,
  availableMedications = [],
  onSubmit,
  serverError,
  isSubmitting,
}: MedicationFormProps) {
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting: formSubmitting },
  } = useForm<MedicationFormValues>({
    resolver: zodResolver(medicationFormSchema),
    defaultValues: { ...EMPTY_DEFAULTS, ...defaultValues },
  });

  const conflictFields = useFieldArray({ control, name: "conflicts" });
  // Single reactive subscription (not per-row `watch()` inside the
  // render map — that returns a function the React Compiler can't
  // memoize: react-hooks/incompatible-library).
  const conflictValues = useWatch({ control, name: "conflicts" }) ?? [];

  const submit: SubmitHandler<MedicationFormValues> = async (values) => {
    await onSubmit(
      toApiBody(values),
      values.conflicts.map((c) => ({
        other_medication_id: c.other_medication_id,
        cooldown_minutes: Number(c.cooldown_minutes),
      })),
    );
  };

  const untracked = useWatch({ control, name: "untracked" });
  const timesPerDay = Number(useWatch({ control, name: "times_per_day" }));
  const timerPreference = useWatch({ control, name: "timer_preference" });

  const submittingNow = isSubmitting || formSubmitting;

  return (
    <form
      onSubmit={handleSubmit(submit)}
      noValidate
      className="space-y-4"
      aria-label={mode === "create" ? "Add medication" : "Edit medication"}
    >
      <div>
        <label htmlFor="name" className="block text-sm font-medium">
          Name
        </label>
        <input
          id="name"
          type="text"
          autoComplete="off"
          className="mt-1 w-full rounded border px-3 py-2"
          {...register("name")}
        />
        {errors.name && (
          <p role="alert" className="mt-1 text-sm text-red-600">
            {errors.name.message}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label
            htmlFor="quantity_per_dose"
            className="block text-sm font-medium"
          >
            Dosage
          </label>
          <input
            id="quantity_per_dose"
            type="text"
            inputMode="decimal"
            className="mt-1 w-full rounded border px-3 py-2"
            {...register("quantity_per_dose")}
          />
          {errors.quantity_per_dose && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.quantity_per_dose.message}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="unit" className="block text-sm font-medium">
            Unit
          </label>
          <input
            id="unit"
            type="text"
            autoComplete="off"
            placeholder="mg"
            className="mt-1 w-full rounded border px-3 py-2"
            {...register("unit")}
          />
          {errors.unit && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.unit.message}
            </p>
          )}
        </div>
      </div>

      <div>
        <label htmlFor="timer_preference" className="block text-sm font-medium">
          Timer mode
        </label>
        <select
          id="timer_preference"
          className="mt-1 w-full rounded border px-3 py-2"
          {...register("timer_preference")}
        >
          <option value="none">None (boolean taken today)</option>
          <option value="count_up">Count up since last dose</option>
          <option value="count_down">Count down (minimum interval)</option>
          <option value="multi_sub_dose">Multi sub-dose (window)</option>
        </select>
      </div>

      {timerPreference === "count_down" && (
        <div>
          <label
            htmlFor="min_interval_minutes"
            className="block text-sm font-medium"
          >
            Minimum interval (minutes)
          </label>
          <input
            id="min_interval_minutes"
            type="number"
            min={1}
            step={1}
            className="mt-1 w-32 rounded border px-3 py-2"
            {...register("min_interval_minutes")}
          />
          {errors.min_interval_minutes && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.min_interval_minutes.message}
            </p>
          )}
        </div>
      )}

      {timerPreference === "multi_sub_dose" && (
        <div>
          <label
            htmlFor="window_duration_minutes"
            className="block text-sm font-medium"
          >
            Window duration (minutes)
          </label>
          <input
            id="window_duration_minutes"
            type="number"
            min={1}
            step={1}
            className="mt-1 w-32 rounded border px-3 py-2"
            {...register("window_duration_minutes")}
          />
          {errors.window_duration_minutes && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.window_duration_minutes.message}
            </p>
          )}
        </div>
      )}

      <div>
        <label htmlFor="times_per_day" className="block text-sm font-medium">
          Times per day
        </label>
        <input
          id="times_per_day"
          type="number"
          min={0}
          max={24}
          step={1}
          className="mt-1 w-32 rounded border px-3 py-2"
          {...register("times_per_day")}
        />
        {errors.times_per_day && (
          <p role="alert" className="mt-1 text-sm text-red-600">
            {errors.times_per_day.message}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="start_date" className="block text-sm font-medium">
            Start date
          </label>
          <input
            id="start_date"
            type="date"
            className="mt-1 w-full rounded border px-3 py-2"
            {...register("start_date")}
          />
          {errors.start_date && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.start_date.message}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="end_date" className="block text-sm font-medium">
            End date
          </label>
          <input
            id="end_date"
            type="date"
            className="mt-1 w-full rounded border px-3 py-2"
            {...register("end_date")}
          />
          {errors.end_date && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.end_date.message}
            </p>
          )}
        </div>
      </div>

      <div>
        <label className="inline-flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" {...register("untracked")} />
          Untracked / As Needed
        </label>
        <p className="text-xs text-gray-600">
          When checked, no fixed total-dose count is recorded.
        </p>
      </div>

      <div>
        <label htmlFor="total_doses" className="block text-sm font-medium">
          Total doses
        </label>
        <input
          id="total_doses"
          type="number"
          min={1}
          step={1}
          disabled={untracked}
          className="mt-1 w-32 rounded border px-3 py-2 disabled:bg-gray-100"
          {...register("total_doses")}
        />
        {errors.total_doses && (
          <p role="alert" className="mt-1 text-sm text-red-600">
            {errors.total_doses.message}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="refill_count" className="block text-sm font-medium">
            Refill count
          </label>
          <input
            id="refill_count"
            type="number"
            min={0}
            step={1}
            className="mt-1 w-full rounded border px-3 py-2"
            {...register("refill_count")}
          />
          {errors.refill_count && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.refill_count.message}
            </p>
          )}
        </div>
        <div>
          <label
            htmlFor="refill_threshold"
            className="block text-sm font-medium"
          >
            Refill threshold
          </label>
          <input
            id="refill_threshold"
            type="number"
            min={0}
            step={1}
            className="mt-1 w-full rounded border px-3 py-2"
            {...register("refill_threshold")}
          />
          {errors.refill_threshold && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.refill_threshold.message}
            </p>
          )}
        </div>
      </div>

      <ScheduleInput
        control={control}
        errors={errors}
        timesPerDay={timesPerDay}
      />

      <fieldset className="rounded border p-3">
        <legend className="px-1 text-sm font-medium">Conflicts with</legend>
        <p className="mb-2 text-xs text-gray-600">
          Pair this medication with another of yours and set a cooldown. The
          rule is symmetric and applies in both directions. To change a
          cooldown, remove the entry and add it again.
        </p>
        {conflictFields.fields.length === 0 && (
          <p className="mb-2 text-xs text-gray-500">
            No interactions configured.
          </p>
        )}
        <ul className="space-y-2">
          {conflictFields.fields.map((field, index) => {
            const currentValue =
              conflictValues[index]?.other_medication_id ?? "";
            const chosenElsewhere = new Set(
              conflictValues
                .map((c, i) => (i === index ? "" : c?.other_medication_id))
                .filter((v): v is string => Boolean(v)),
            );
            return (
              <li key={field.id} className="flex items-end gap-2">
                <div className="grow">
                  <label
                    htmlFor={`conflict-med-${index}`}
                    className="block text-xs font-medium"
                  >
                    Medication
                  </label>
                  <select
                    id={`conflict-med-${index}`}
                    className="mt-1 w-full rounded border px-2 py-1.5 text-sm"
                    {...register(`conflicts.${index}.other_medication_id`)}
                  >
                    <option value="">Select…</option>
                    {availableMedications
                      .filter(
                        (m) =>
                          !chosenElsewhere.has(m.id) || m.id === currentValue,
                      )
                      .map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name}
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label
                    htmlFor={`conflict-cd-${index}`}
                    className="block text-xs font-medium"
                  >
                    Cooldown (min)
                  </label>
                  <input
                    id={`conflict-cd-${index}`}
                    type="number"
                    min={1}
                    step={1}
                    className="mt-1 w-28 rounded border px-2 py-1.5 text-sm"
                    {...register(`conflicts.${index}.cooldown_minutes`)}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => conflictFields.remove(index)}
                  className="rounded border border-red-300 px-2 py-1.5 text-sm text-red-700"
                >
                  Remove
                </button>
              </li>
            );
          })}
        </ul>
        {Array.isArray(errors.conflicts) &&
          errors.conflicts.map((e, i) =>
            e ? (
              <p key={i} role="alert" className="mt-1 text-xs text-red-600">
                {e.other_medication_id?.message ?? e.cooldown_minutes?.message}
              </p>
            ) : null,
          )}
        {!Array.isArray(errors.conflicts) && errors.conflicts?.message && (
          <p role="alert" className="mt-1 text-xs text-red-600">
            {errors.conflicts.message}
          </p>
        )}
        <button
          type="button"
          onClick={() =>
            conflictFields.append({
              other_medication_id: "",
              cooldown_minutes: "",
            })
          }
          disabled={availableMedications.length === 0}
          className="mt-2 rounded border px-3 py-1.5 text-sm disabled:opacity-50"
        >
          Add interaction
        </button>
        {availableMedications.length === 0 && (
          <p className="mt-1 text-xs text-gray-500">
            Add another medication first to configure interactions.
          </p>
        )}
      </fieldset>

      {serverError && (
        <p role="alert" className="text-sm text-red-600">
          {serverError}
        </p>
      )}

      <button
        type="submit"
        disabled={submittingNow}
        className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
      >
        {submittingNow
          ? "Saving…"
          : mode === "create"
            ? "Add medication"
            : "Save changes"}
      </button>
    </form>
  );
}
