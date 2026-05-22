import { useState } from "react";
import { useController, type Control, type FieldErrors } from "react-hook-form";
import {
  useCreateSchedule,
  useSchedules,
  type ScheduleOut,
} from "@/hooks/useSchedules";
import type { MedicationFormValues } from "./medicationFormSchema";

interface SchedulePickerProps {
  control: Control<MedicationFormValues>;
  errors: FieldErrors<MedicationFormValues>;
  /** ``times_per_day`` from the form — used for the parity heads-up. */
  timesPerDay: number;
}

function formatTimeOfDay(t: string): string {
  // Server returns "HH:MM:SS"; trim seconds for display.
  return t.slice(0, 5);
}

function displayLabel(schedule: ScheduleOut): string {
  return schedule.label.trim() === ""
    ? formatTimeOfDay(schedule.time_of_day)
    : `${schedule.label} (${formatTimeOfDay(schedule.time_of_day)})`;
}

/**
 * Multi-select chips + inline "Add new" form for the user's shared
 * schedules. Replaces the legacy per-med ``ScheduleInput`` (which
 * created Schedule rows server-side from raw HH:MM input).
 */
export function SchedulePicker({
  control,
  errors,
  timesPerDay,
}: SchedulePickerProps) {
  const { field } = useController({
    control,
    name: "selected_schedule_ids",
  });
  const selected: string[] = field.value ?? [];

  const { data: schedules = [], isLoading, isError } = useSchedules();
  const createSchedule = useCreateSchedule();

  const [showAdd, setShowAdd] = useState(false);
  const [newTime, setNewTime] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);

  const toggle = (id: string) => {
    if (selected.includes(id)) {
      field.onChange(selected.filter((x) => x !== id));
    } else {
      field.onChange([...selected, id]);
    }
  };

  const handleAdd = async () => {
    if (newTime === "") {
      setSubmitError("Pick a time of day.");
      return;
    }
    setSubmitError(null);
    try {
      const created = await createSchedule.mutateAsync({
        time_of_day: newTime,
        label: newLabel.trim(),
        days_of_week: 127,
      });
      // Auto-select the new schedule.
      field.onChange([...selected, created.id]);
      setNewTime("");
      setNewLabel("");
      setShowAdd(false);
    } catch (e) {
      setSubmitError(
        e instanceof Error ? e.message : "Failed to create schedule.",
      );
    }
  };

  const mismatch =
    Number.isFinite(timesPerDay) && timesPerDay !== selected.length;

  return (
    <fieldset className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
      <legend className="px-1 text-sm font-medium">Schedules</legend>
      <p className="text-xs text-gray-600">
        Pick existing time slots (or add new ones). Schedules are shared across
        all your medications — editing them here affects every medication
        attached to the same slot.
      </p>

      {isLoading && (
        <p className="mt-2 text-sm text-gray-500">Loading schedules…</p>
      )}
      {isError && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          Failed to load schedules.
        </p>
      )}

      {!isLoading && !isError && schedules.length === 0 && (
        <p className="mt-2 text-sm italic text-gray-500">
          No schedules yet — add one below.
        </p>
      )}

      {schedules.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-2">
          {schedules.map((s) => {
            const isSelected = selected.includes(s.id);
            return (
              <li key={s.id}>
                <button
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => toggle(s.id)}
                  className={
                    isSelected
                      ? "rounded-full bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700"
                      : "rounded-full border border-gray-300 px-3 py-1 text-sm hover:bg-gray-50"
                  }
                >
                  {displayLabel(s)}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {errors.selected_schedule_ids && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {errors.selected_schedule_ids.message?.toString()}
        </p>
      )}

      <div className="mt-3">
        {!showAdd && (
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className="rounded border px-3 py-1 text-sm hover:bg-gray-50"
          >
            + Add a new schedule
          </button>
        )}
        {showAdd && (
          <div className="rounded border bg-gray-50 p-3">
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <label
                  htmlFor="new-sched-time"
                  className="block text-xs font-medium"
                >
                  Time
                </label>
                <input
                  id="new-sched-time"
                  type="time"
                  value={newTime}
                  onChange={(e) => setNewTime(e.target.value)}
                  className="mt-1 rounded border px-2 py-1 text-sm"
                />
              </div>
              <div className="grow">
                <label
                  htmlFor="new-sched-label"
                  className="block text-xs font-medium"
                >
                  Label (optional)
                </label>
                <input
                  id="new-sched-label"
                  type="text"
                  value={newLabel}
                  onChange={(e) => setNewLabel(e.target.value)}
                  placeholder="Morning"
                  className="mt-1 w-full rounded border px-2 py-1 text-sm"
                />
              </div>
              <button
                type="button"
                onClick={handleAdd}
                disabled={createSchedule.isPending}
                className="rounded bg-blue-600 px-3 py-1 text-sm text-white disabled:opacity-50"
              >
                {createSchedule.isPending ? "Adding…" : "Add"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowAdd(false);
                  setNewTime("");
                  setNewLabel("");
                  setSubmitError(null);
                }}
                className="rounded border px-3 py-1 text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
            {submitError && (
              <p role="alert" className="mt-2 text-sm text-red-600">
                {submitError}
              </p>
            )}
          </div>
        )}
      </div>

      {mismatch && (
        <p
          role="alert"
          className="mt-3 rounded bg-yellow-50 px-2 py-1 text-sm text-yellow-800"
        >
          Heads up: you set <strong>{timesPerDay}</strong> times per day but
          have <strong>{selected.length}</strong> schedule
          {selected.length === 1 ? "" : "s"} attached.
        </p>
      )}
    </fieldset>
  );
}
