import {
  useForm,
  useFieldArray,
  useWatch,
  type SubmitHandler,
} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { components } from "@/api/v1";
import {
  durationToMinutes,
  medicationFormSchema,
  type MedicationFormValues,
} from "./medicationFormSchema";
import { SchedulePicker } from "./SchedulePicker";

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
  unit: "mg",
  times_per_day: "1",
  start_date: "",
  end_date: "",
  untracked: false,
  total_doses: "",
  refill_count: "",
  refill_threshold: "",
  timer_preference: "none",
  min_interval_value: "",
  min_interval_unit: "hour",
  window_duration_value: "",
  window_duration_unit: "hour",
  pill_based: true,
  pill_strength: "",
  pills_per_dose: "",
  max_doses_per_day: "",
  selected_schedule_ids: [],
  conflicts: [],
};

function toApiBody(values: MedicationFormValues): MedicationBody {
  const intOrNull = (v: string): number | null => (v === "" ? null : Number(v));
  // Pill-based: derive quantity from pill_strength * pills_per_dose.
  // Otherwise honor the user's literal quantity_per_dose.
  const derivedQuantity = values.pill_based
    ? String(
        Number(values.pill_strength || "0") *
          Number(values.pills_per_dose || "0"),
      )
    : values.quantity_per_dose;
  return {
    name: values.name.trim(),
    quantity_per_dose: derivedQuantity,
    unit: values.unit.trim(),
    times_per_day: Number(values.times_per_day),
    start_date: values.start_date === "" ? null : values.start_date,
    end_date: values.end_date === "" ? null : values.end_date,
    total_doses: values.untracked ? null : intOrNull(values.total_doses),
    refill_count: intOrNull(values.refill_count),
    refill_threshold: intOrNull(values.refill_threshold),
    timer_preference: values.timer_preference,
    min_interval_minutes:
      values.timer_preference === "count_down"
        ? durationToMinutes(values.min_interval_value, values.min_interval_unit)
        : null,
    window_duration_minutes:
      values.timer_preference === "multi_sub_dose"
        ? durationToMinutes(
            values.window_duration_value,
            values.window_duration_unit,
          )
        : null,
    pill_strength: values.pill_based ? values.pill_strength : null,
    pills_per_dose: values.pill_based ? Number(values.pills_per_dose) : null,
    max_doses_per_day:
      values.timer_preference === "multi_sub_dose"
        ? intOrNull(values.max_doses_per_day)
        : null,
    schedules: values.selected_schedule_ids,
  };
}

const COMMON_UNITS = ["mg", "ml", "mcg", "g", "tablet", "capsule", "drop"];

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
  const pillBased = useWatch({ control, name: "pill_based" });
  const pillStrength = useWatch({ control, name: "pill_strength" });
  const pillsPerDose = useWatch({ control, name: "pills_per_dose" });
  const unit = useWatch({ control, name: "unit" });

  const submittingNow = isSubmitting || formSubmitting;
  const timesPerDayLabel =
    timerPreference === "multi_sub_dose"
      ? "Max doses at a time"
      : "Times per day";
  const timesPerDayHint =
    timerPreference === "multi_sub_dose"
      ? "The most overlapping doses allowed at once; each dose stays active for the window above."
      : "How many scheduled doses per day.";

  const derivedQuantity =
    pillBased &&
    pillStrength !== "" &&
    pillsPerDose !== "" &&
    Number.isFinite(Number(pillStrength)) &&
    Number.isFinite(Number(pillsPerDose))
      ? Number(pillStrength) * Number(pillsPerDose)
      : null;

  return (
    <form
      onSubmit={handleSubmit(submit)}
      noValidate
      className="space-y-4"
      aria-label={mode === "create" ? "Add medication" : "Edit medication"}
    >
      <aside className="rounded border border-blue-200 bg-blue-50 p-3 text-sm text-gray-700">
        <p className="font-medium text-blue-900">Timer modes</p>
        <ul className="mt-1 list-disc space-y-1 pl-5 text-xs">
          <li>
            <strong>None</strong> — record taken/not-taken per scheduled slot.
          </li>
          <li>
            <strong>Count up</strong> — show how long since the last dose.
          </li>
          <li>
            <strong>Count down</strong> — block doses inside a minimum interval
            (overdose guard).
          </li>
          <li>
            <strong>Multi sub-dose</strong> — each dose opens its own rolling
            window; cap how many overlap at once (and optionally per day).
          </li>
        </ul>
      </aside>

      <div>
        <label htmlFor="name" className="block text-sm font-medium">
          Name
        </label>
        <input
          id="name"
          type="text"
          autoComplete="off"
          className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
          {...register("name")}
        />
        {errors.name && (
          <p role="alert" className="mt-1 text-sm text-red-600">
            {errors.name.message}
          </p>
        )}
      </div>

      <fieldset className="rounded-xl border border-slate-200 bg-white p-4">
        <legend className="px-1 text-sm font-medium">Dosage</legend>
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" {...register("pill_based")} />
          Pill-based (count pills, derive dose)
        </label>
        <p className="mt-1 text-xs text-gray-600">
          Check this for tablets/capsules where you take a whole number of pills
          each dose. We&apos;ll multiply the per-pill strength by the
          pills-per-dose to get the actual dose.
        </p>

        {!pillBased && (
          <div className="mt-3 grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="quantity_per_dose"
                className="block text-sm font-medium"
              >
                Quantity per dose
              </label>
              <input
                id="quantity_per_dose"
                type="text"
                inputMode="decimal"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
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
                list="med-units"
                autoComplete="off"
                placeholder="mg"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
                {...register("unit")}
              />
              <datalist id="med-units">
                {COMMON_UNITS.map((u) => (
                  <option key={u} value={u} />
                ))}
              </datalist>
              {errors.unit && (
                <p role="alert" className="mt-1 text-sm text-red-600">
                  {errors.unit.message}
                </p>
              )}
            </div>
          </div>
        )}

        {pillBased && (
          <div className="mt-3 space-y-3">
            <div className="grid grid-cols-[1fr_8rem] gap-3">
              <div>
                <label
                  htmlFor="pill_strength"
                  className="block text-sm font-medium"
                >
                  Strength per pill
                </label>
                <input
                  id="pill_strength"
                  type="text"
                  inputMode="decimal"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
                  {...register("pill_strength")}
                />
                {errors.pill_strength && (
                  <p role="alert" className="mt-1 text-sm text-red-600">
                    {errors.pill_strength.message}
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
                  list="med-units"
                  autoComplete="off"
                  placeholder="mg"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
                  {...register("unit")}
                />
                <datalist id="med-units">
                  {COMMON_UNITS.map((u) => (
                    <option key={u} value={u} />
                  ))}
                </datalist>
                {errors.unit && (
                  <p role="alert" className="mt-1 text-sm text-red-600">
                    {errors.unit.message}
                  </p>
                )}
              </div>
            </div>
            <div>
              <label
                htmlFor="pills_per_dose"
                className="block text-sm font-medium"
              >
                Pills per dose
              </label>
              <input
                id="pills_per_dose"
                type="number"
                min={1}
                step={1}
                className="mt-1 w-32 rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
                {...register("pills_per_dose")}
              />
              {errors.pills_per_dose && (
                <p role="alert" className="mt-1 text-sm text-red-600">
                  {errors.pills_per_dose.message}
                </p>
              )}
            </div>
            {derivedQuantity !== null && (
              <p className="text-sm text-gray-700">
                Effective dose:{" "}
                <strong>
                  {derivedQuantity} {unit}
                </strong>
              </p>
            )}
          </div>
        )}
      </fieldset>

      <div>
        <label htmlFor="timer_preference" className="block text-sm font-medium">
          Timer mode
        </label>
        <select
          id="timer_preference"
          className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
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
            htmlFor="min_interval_value"
            className="block text-sm font-medium"
          >
            Minimum interval
          </label>
          <p className="text-xs text-gray-600">
            Blocks the next dose until this much time has passed.
          </p>
          <div className="mt-1 flex items-center gap-2">
            <input
              id="min_interval_value"
              type="number"
              min={1}
              step={1}
              className="w-24 rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
              {...register("min_interval_value")}
            />
            <select
              aria-label="Interval unit"
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
              {...register("min_interval_unit")}
            >
              <option value="min">minutes</option>
              <option value="hour">hours</option>
              <option value="day">days</option>
            </select>
          </div>
          {errors.min_interval_value && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.min_interval_value.message}
            </p>
          )}
        </div>
      )}

      {timerPreference === "multi_sub_dose" && (
        <div>
          <label
            htmlFor="window_duration_value"
            className="block text-sm font-medium"
          >
            Window duration
          </label>
          <p className="text-xs text-gray-600">
            How long each rolling window lasts (e.g., 6 hours).
          </p>
          <div className="mt-1 flex items-center gap-2">
            <input
              id="window_duration_value"
              type="number"
              min={1}
              step={1}
              className="w-24 rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
              {...register("window_duration_value")}
            />
            <select
              aria-label="Window unit"
              className="rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
              {...register("window_duration_unit")}
            >
              <option value="min">minutes</option>
              <option value="hour">hours</option>
              <option value="day">days</option>
            </select>
          </div>
          {errors.window_duration_value && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.window_duration_value.message}
            </p>
          )}
        </div>
      )}

      <div>
        <label htmlFor="times_per_day" className="block text-sm font-medium">
          {timesPerDayLabel}
        </label>
        <p className="text-xs text-gray-600">{timesPerDayHint}</p>
        <input
          id="times_per_day"
          type="number"
          min={0}
          max={24}
          step={1}
          className="mt-1 w-32 rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
          {...register("times_per_day")}
        />
        {errors.times_per_day && (
          <p role="alert" className="mt-1 text-sm text-red-600">
            {errors.times_per_day.message}
          </p>
        )}
      </div>

      {timerPreference === "multi_sub_dose" && (
        <div>
          <label
            htmlFor="max_doses_per_day"
            className="block text-sm font-medium"
          >
            Max doses per day (optional)
          </label>
          <p className="text-xs text-gray-600">
            Hard cap across the whole day, on top of the max-at-a-time cap
            above. Leave blank for no daily cap.
          </p>
          <input
            id="max_doses_per_day"
            type="number"
            min={1}
            step={1}
            className="mt-1 w-32 rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
            {...register("max_doses_per_day")}
          />
          {errors.max_doses_per_day && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.max_doses_per_day.message}
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="start_date" className="block text-sm font-medium">
            Start date
          </label>
          <input
            id="start_date"
            type="date"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
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
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
            {...register("end_date")}
          />
          {errors.end_date && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.end_date.message}
            </p>
          )}
        </div>
      </div>

      <fieldset className="rounded-xl border border-slate-200 bg-white p-4">
        <legend className="px-1 text-sm font-medium">Course length</legend>
        <p className="text-xs text-gray-600">
          For a fixed course (e.g. a 14-day antibiotic) — the total number of
          doses it runs from start to finish. This is the size of the
          prescription, not how much you have on hand right now.
        </p>

        <label className="mt-3 inline-flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" {...register("untracked")} />
          Untracked / As Needed
        </label>
        <p className="text-xs text-gray-600">
          Check this for ongoing or as-needed meds that have no fixed course
          length.
        </p>

        <div className="mt-3">
          <label htmlFor="total_doses" className="block text-sm font-medium">
            Total doses
          </label>
          <p className="text-xs text-gray-600">
            Total doses in the whole course.
          </p>
          <input
            id="total_doses"
            type="number"
            min={1}
            step={1}
            disabled={untracked}
            className="mt-1 w-32 rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30 disabled:bg-gray-100"
            {...register("total_doses")}
          />
          {errors.total_doses && (
            <p role="alert" className="mt-1 text-sm text-red-600">
              {errors.total_doses.message}
            </p>
          )}
        </div>
      </fieldset>

      <fieldset className="rounded-xl border border-slate-200 bg-white p-4">
        <legend className="px-1 text-sm font-medium">
          Supply &amp; refills
        </legend>
        <p className="text-xs text-gray-600">
          How much you have on hand now and when to be reminded to refill —
          separate from the course length above.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="refill_count" className="block text-sm font-medium">
              {pillBased ? "Pills on hand" : "Refill count"}
            </label>
            <input
              id="refill_count"
              type="number"
              min={0}
              step={1}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
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
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
              {...register("refill_threshold")}
            />
            {errors.refill_threshold && (
              <p role="alert" className="mt-1 text-sm text-red-600">
                {errors.refill_threshold.message}
              </p>
            )}
          </div>
        </div>
      </fieldset>

      <SchedulePicker
        control={control}
        errors={errors}
        timesPerDay={timesPerDay}
        showParity={timerPreference !== "multi_sub_dose"}
      />

      <fieldset className="rounded-xl border border-slate-200 bg-white p-4">
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
        className="w-full rounded-xl bg-blue-600 px-4 py-2.5 font-semibold text-white shadow-sm transition hover:bg-blue-700 active:scale-[0.98] disabled:opacity-50"
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
