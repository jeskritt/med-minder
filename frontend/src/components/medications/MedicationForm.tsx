import { useForm, type SubmitHandler } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { components } from "@/api/v1";
import {
  medicationFormSchema,
  type MedicationFormValues,
} from "./medicationFormSchema";
import { ScheduleInput } from "./ScheduleInput";

type MedicationBody = components["schemas"]["MedicationBody"];
type MedicationOut = components["schemas"]["MedicationOut"];

export interface MedicationFormProps {
  /** ``"create"`` or ``"edit"`` mode — controls submit button label only. */
  mode: "create" | "edit";
  /** Initial values, e.g. when editing.  Optional. */
  defaultValues?: Partial<MedicationFormValues>;
  /** Called with the API-shaped body once the form is valid. */
  onSubmit: (body: MedicationBody) => Promise<void> | void;
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
  schedules: [],
};

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
    schedules: med.schedules.map((s) => ({
      time_of_day: s.time_of_day.slice(0, 5),
    })),
  };
}

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
    schedules: values.schedules.map((s) => s.time_of_day),
  };
}

export function MedicationForm({
  mode,
  defaultValues,
  onSubmit,
  serverError,
  isSubmitting,
}: MedicationFormProps) {
  const {
    register,
    handleSubmit,
    watch,
    control,
    formState: { errors, isSubmitting: formSubmitting },
  } = useForm<MedicationFormValues>({
    resolver: zodResolver(medicationFormSchema),
    defaultValues: { ...EMPTY_DEFAULTS, ...defaultValues },
  });

  const submit: SubmitHandler<MedicationFormValues> = async (values) => {
    await onSubmit(toApiBody(values));
  };

  const untracked = watch("untracked");
  const timesPerDayRaw = watch("times_per_day");
  const timesPerDay = Number(timesPerDayRaw);

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
