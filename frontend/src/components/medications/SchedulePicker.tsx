import { useState } from "react";
import { useController, type Control, type FieldErrors } from "react-hook-form";
import {
  useCreateSchedule,
  useDeleteSchedule,
  useSchedules,
  useUpdateSchedule,
  type ScheduleOut,
} from "@/hooks/useSchedules";
import type { MedicationFormValues } from "./medicationFormSchema";

interface SchedulePickerProps {
  control: Control<MedicationFormValues>;
  errors: FieldErrors<MedicationFormValues>;
  /** ``times_per_day`` from the form — used for the parity heads-up. */
  timesPerDay: number;
  /**
   * Whether the times-per-day↔schedule-count parity warning applies. It
   * doesn't for ``multi_sub_dose`` (there ``times_per_day`` is a
   * max-at-a-time cap, not a count of scheduled slots).
   */
  showParity?: boolean;
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
 * Multi-select chips + inline "Add new" / edit / delete for the user's
 * shared schedules. Replaces the legacy per-med ``ScheduleInput`` (which
 * created Schedule rows server-side from raw HH:MM input).
 */
export function SchedulePicker({
  control,
  errors,
  timesPerDay,
  showParity = true,
}: SchedulePickerProps) {
  const { field } = useController({
    control,
    name: "selected_schedule_ids",
  });
  const selected: string[] = field.value ?? [];

  const { data: schedules = [], isLoading, isError } = useSchedules();
  const createSchedule = useCreateSchedule();
  const updateSchedule = useUpdateSchedule();
  const deleteSchedule = useDeleteSchedule();

  const [showAdd, setShowAdd] = useState(false);
  const [newTime, setNewTime] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTime, setEditTime] = useState("");
  const [editLabel, setEditLabel] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  const [deletingId, setDeletingId] = useState<string | null>(null);

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

  const startEdit = (s: ScheduleOut) => {
    setEditingId(s.id);
    setEditTime(formatTimeOfDay(s.time_of_day));
    setEditLabel(s.label);
    setEditError(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditError(null);
  };

  const handleEditSave = async (s: ScheduleOut) => {
    if (editTime === "") {
      setEditError("Pick a time of day.");
      return;
    }
    setEditError(null);
    try {
      await updateSchedule.mutateAsync({
        id: s.id,
        body: {
          time_of_day: editTime,
          label: editLabel.trim(),
          days_of_week: s.days_of_week,
        },
      });
      setEditingId(null);
    } catch (e) {
      setEditError(
        e instanceof Error ? e.message : "Failed to update schedule.",
      );
    }
  };

  const deleting = schedules.find((s) => s.id === deletingId) ?? null;

  const handleDeleteConfirm = async () => {
    if (deleting === null) return;
    try {
      await deleteSchedule.mutateAsync(deleting.id);
      // Drop it from the current selection if it was attached here.
      if (selected.includes(deleting.id)) {
        field.onChange(selected.filter((x) => x !== deleting.id));
      }
      setDeletingId(null);
    } catch {
      // Leave the modal open; the list query will surface load errors.
      setDeletingId(null);
    }
  };

  const mismatch =
    showParity &&
    Number.isFinite(timesPerDay) &&
    timesPerDay !== selected.length;

  return (
    <fieldset className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
      <legend className="px-1 text-sm font-medium">Schedules</legend>
      <p className="text-xs text-gray-600">
        Pick existing time slots (or add new ones). Schedules are shared across
        all your medications — editing or deleting one here affects every
        medication attached to the same slot.
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
            if (editingId === s.id) {
              return (
                <li key={s.id} className="w-full">
                  <div className="rounded border bg-gray-50 p-3">
                    <div className="flex flex-wrap items-end gap-2">
                      <div>
                        <label
                          htmlFor={`edit-sched-time-${s.id}`}
                          className="block text-xs font-medium"
                        >
                          Time
                        </label>
                        <input
                          id={`edit-sched-time-${s.id}`}
                          type="time"
                          value={editTime}
                          onChange={(e) => setEditTime(e.target.value)}
                          className="mt-1 rounded border px-2 py-1 text-sm"
                        />
                      </div>
                      <div className="grow">
                        <label
                          htmlFor={`edit-sched-label-${s.id}`}
                          className="block text-xs font-medium"
                        >
                          Label (optional)
                        </label>
                        <input
                          id={`edit-sched-label-${s.id}`}
                          type="text"
                          value={editLabel}
                          onChange={(e) => setEditLabel(e.target.value)}
                          placeholder="Morning"
                          className="mt-1 w-full rounded border px-2 py-1 text-sm"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleEditSave(s)}
                        disabled={updateSchedule.isPending}
                        className="rounded bg-blue-600 px-3 py-1 text-sm text-white disabled:opacity-50"
                      >
                        {updateSchedule.isPending ? "Saving…" : "Save"}
                      </button>
                      <button
                        type="button"
                        onClick={cancelEdit}
                        className="rounded border px-3 py-1 text-sm hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                    </div>
                    {editError && (
                      <p role="alert" className="mt-2 text-sm text-red-600">
                        {editError}
                      </p>
                    )}
                  </div>
                </li>
              );
            }
            const isSelected = selected.includes(s.id);
            return (
              <li key={s.id} className="inline-flex items-center">
                <span
                  className={
                    isSelected
                      ? "inline-flex items-center gap-1 rounded-full bg-blue-600 px-2 py-1 text-sm text-white"
                      : "inline-flex items-center gap-1 rounded-full border border-gray-300 px-2 py-1 text-sm"
                  }
                >
                  <button
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => toggle(s.id)}
                    className="px-1 hover:underline"
                  >
                    {displayLabel(s)}
                  </button>
                  <button
                    type="button"
                    aria-label={`Edit ${displayLabel(s)}`}
                    onClick={() => startEdit(s)}
                    className={
                      isSelected
                        ? "rounded px-1 text-white/90 hover:text-white"
                        : "rounded px-1 text-gray-500 hover:text-gray-800"
                    }
                  >
                    ✎
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${displayLabel(s)}`}
                    onClick={() => setDeletingId(s.id)}
                    className={
                      isSelected
                        ? "rounded px-1 text-white/90 hover:text-white"
                        : "rounded px-1 text-gray-500 hover:text-red-700"
                    }
                  >
                    🗑
                  </button>
                </span>
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

      {deleting !== null && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Delete schedule"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        >
          <div className="w-full max-w-sm rounded-xl bg-white p-4 shadow-lg">
            <h2 className="text-base font-semibold">
              Delete “{displayLabel(deleting)}”?
            </h2>
            {(deleting.medications ?? []).length > 0 ? (
              <>
                <p className="mt-2 text-sm text-gray-700">
                  This schedule is attached to:
                </p>
                <ul className="mt-1 list-disc pl-5 text-sm text-gray-700">
                  {(deleting.medications ?? []).map((m) => (
                    <li key={m.id}>{m.name}</li>
                  ))}
                </ul>
                <p className="mt-2 text-sm text-gray-700">
                  They will be unscheduled (not deleted).
                </p>
              </>
            ) : (
              <p className="mt-2 text-sm text-gray-700">
                No medications are attached to this schedule.
              </p>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeletingId(null)}
                className="rounded border px-3 py-1.5 text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleDeleteConfirm()}
                disabled={deleteSchedule.isPending}
                className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {deleteSchedule.isPending ? "Deleting…" : "Delete schedule"}
              </button>
            </div>
          </div>
        </div>
      )}
    </fieldset>
  );
}
