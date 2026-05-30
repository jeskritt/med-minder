import { useState } from "react";
import { useController, type Control, type FieldErrors } from "react-hook-form";
import { Pencil } from "lucide-react";
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

const SMALL_INPUT = "mm-input mt-1 py-1.5 text-sm";

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
  const [confirmingMoveId, setConfirmingMoveId] = useState<string | null>(null);

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
    setConfirmingMoveId(null);
  };

  const doUpdate = async (s: ScheduleOut) => {
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

  const handleEditSave = async (s: ScheduleOut) => {
    if (editTime === "") {
      setEditError("Pick a time of day.");
      return;
    }
    setEditError(null);
    // Moving a shared time shifts every attached med — confirm first
    // (mirrors the delete guard). Label-only edits or unattached
    // schedules save directly.
    const timeChanged = editTime !== formatTimeOfDay(s.time_of_day);
    const attached = s.medications ?? [];
    if (timeChanged && attached.length > 0) {
      setConfirmingMoveId(s.id);
      return;
    }
    await doUpdate(s);
  };

  const confirmingMove =
    schedules.find((s) => s.id === confirmingMoveId) ?? null;

  const deleting = schedules.find((s) => s.id === deletingId) ?? null;

  const handleDeleteConfirm = async () => {
    if (deleting === null) return;
    try {
      await deleteSchedule.mutateAsync(deleting.id);
      // Drop it from the current selection if it was attached here.
      if (selected.includes(deleting.id)) {
        field.onChange(selected.filter((x) => x !== deleting.id));
      }
      // Close the edit panel too (delete is triggered from inside it).
      if (editingId === deleting.id) {
        setEditingId(null);
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
    <fieldset className="mm-card mt-4 space-y-1 p-4">
      <legend className="px-1 text-sm font-semibold text-foreground">
        Schedules
      </legend>
      <p className="text-xs text-muted-foreground">
        Pick existing time slots (or add new ones). Schedules are shared across
        all your medications — editing or deleting one here affects every
        medication attached to the same slot.
      </p>

      {isLoading && (
        <p className="mt-2 text-sm text-muted-foreground">Loading schedules…</p>
      )}
      {isError && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          Failed to load schedules.
        </p>
      )}

      {!isLoading && !isError && schedules.length === 0 && (
        <p className="mt-2 text-sm italic text-muted-foreground">
          No schedules yet — add one below.
        </p>
      )}

      {schedules.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-2">
          {schedules.map((s) => {
            if (editingId === s.id) {
              return (
                <li key={s.id} className="w-full">
                  <div className="rounded-xl border border-border bg-muted/50 p-3">
                    <div className="flex flex-wrap items-end gap-2">
                      <div>
                        <label
                          htmlFor={`edit-sched-time-${s.id}`}
                          className="block text-xs font-medium text-foreground"
                        >
                          Time
                        </label>
                        <input
                          id={`edit-sched-time-${s.id}`}
                          type="time"
                          value={editTime}
                          onChange={(e) => setEditTime(e.target.value)}
                          className={`${SMALL_INPUT} w-auto`}
                        />
                      </div>
                      <div className="grow">
                        <label
                          htmlFor={`edit-sched-label-${s.id}`}
                          className="block text-xs font-medium text-foreground"
                        >
                          Label (optional)
                        </label>
                        <input
                          id={`edit-sched-label-${s.id}`}
                          type="text"
                          value={editLabel}
                          onChange={(e) => setEditLabel(e.target.value)}
                          placeholder="Morning"
                          className={SMALL_INPUT}
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleEditSave(s)}
                        disabled={updateSchedule.isPending}
                        className="mm-btn mm-btn-primary"
                      >
                        {updateSchedule.isPending ? "Saving…" : "Save"}
                      </button>
                      <button
                        type="button"
                        onClick={cancelEdit}
                        className="mm-btn mm-btn-secondary"
                      >
                        Cancel
                      </button>
                      {/* Delete is reached from inside the edit panel
                          (not the chip) and routes through the existing
                          confirm modal; ml-auto keeps it clear of Save. */}
                      <button
                        type="button"
                        aria-label={`Delete ${displayLabel(s)}`}
                        onClick={() => setDeletingId(s.id)}
                        className="mm-btn mm-btn-danger ml-auto"
                      >
                        Delete schedule
                      </button>
                    </div>
                    {editError && (
                      <p role="alert" className="mt-2 text-sm text-destructive">
                        {editError}
                      </p>
                    )}
                  </div>
                </li>
              );
            }
            const isSelected = selected.includes(s.id);
            return (
              <li key={s.id} className="inline-flex items-center gap-1">
                {/* Select toggle — comfortable (~44px) touch height. */}
                <button
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => toggle(s.id)}
                  className={
                    isSelected
                      ? "inline-flex min-h-11 items-center rounded-full bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:bg-primary/90"
                      : "inline-flex min-h-11 items-center rounded-full border border-input bg-card px-4 text-sm transition hover:bg-muted"
                  }
                >
                  {displayLabel(s)}
                </button>
                {/* Single ~44px Edit affordance; Delete lives in the edit
                    panel so there's no destructive icon to mis-tap here. */}
                <button
                  type="button"
                  aria-label={`Edit ${displayLabel(s)}`}
                  onClick={() => startEdit(s)}
                  className="inline-flex size-11 items-center justify-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/35"
                >
                  <Pencil className="size-4" />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {errors.selected_schedule_ids && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {errors.selected_schedule_ids.message?.toString()}
        </p>
      )}

      <div className="mt-3">
        {!showAdd && (
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className="mm-btn mm-btn-secondary"
          >
            + Add a new schedule
          </button>
        )}
        {showAdd && (
          <div className="rounded-xl border border-border bg-muted/50 p-3">
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <label
                  htmlFor="new-sched-time"
                  className="block text-xs font-medium text-foreground"
                >
                  Time
                </label>
                <input
                  id="new-sched-time"
                  type="time"
                  value={newTime}
                  onChange={(e) => setNewTime(e.target.value)}
                  className={`${SMALL_INPUT} w-auto`}
                />
              </div>
              <div className="grow">
                <label
                  htmlFor="new-sched-label"
                  className="block text-xs font-medium text-foreground"
                >
                  Label (optional)
                </label>
                <input
                  id="new-sched-label"
                  type="text"
                  value={newLabel}
                  onChange={(e) => setNewLabel(e.target.value)}
                  placeholder="Morning"
                  className={SMALL_INPUT}
                />
              </div>
              <button
                type="button"
                onClick={handleAdd}
                disabled={createSchedule.isPending}
                className="mm-btn mm-btn-primary"
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
                className="mm-btn mm-btn-secondary"
              >
                Cancel
              </button>
            </div>
            {submitError && (
              <p role="alert" className="mt-2 text-sm text-destructive">
                {submitError}
              </p>
            )}
          </div>
        )}
      </div>

      {mismatch && (
        <p
          role="alert"
          className="mt-3 rounded-lg bg-warning/15 px-3 py-1.5 text-sm text-warning-foreground"
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
          className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4 backdrop-blur-sm"
        >
          <div className="mm-card w-full max-w-sm p-5 shadow-lg">
            <h2 className="text-base font-semibold text-foreground">
              Delete “{displayLabel(deleting)}”?
            </h2>
            {(deleting.medications ?? []).length > 0 ? (
              <>
                <p className="mt-2 text-sm text-muted-foreground">
                  This schedule is attached to:
                </p>
                <ul className="mt-1 list-disc pl-5 text-sm text-foreground">
                  {(deleting.medications ?? []).map((m) => (
                    <li key={m.id}>{m.name}</li>
                  ))}
                </ul>
                <p className="mt-2 text-sm text-muted-foreground">
                  They will be unscheduled (not deleted).
                </p>
              </>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">
                No medications are attached to this schedule.
              </p>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeletingId(null)}
                className="mm-btn mm-btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleDeleteConfirm()}
                disabled={deleteSchedule.isPending}
                className="mm-btn mm-btn-danger"
              >
                {deleteSchedule.isPending ? "Deleting…" : "Delete schedule"}
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmingMove !== null && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Move schedule time"
          className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4 backdrop-blur-sm"
        >
          <div className="mm-card w-full max-w-sm p-5 shadow-lg">
            <h2 className="text-base font-semibold text-foreground">
              Move “{displayLabel(confirmingMove)}” to {editTime}?
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              This time is shared by:
            </p>
            <ul className="mt-1 list-disc pl-5 text-sm text-foreground">
              {(confirmingMove.medications ?? []).map((m) => (
                <li key={m.id}>{m.name}</li>
              ))}
            </ul>
            <p className="mt-2 text-sm text-muted-foreground">
              Their reminders and Today slots all shift.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmingMoveId(null)}
                className="mm-btn mm-btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  const target = confirmingMove;
                  setConfirmingMoveId(null);
                  void doUpdate(target);
                }}
                disabled={updateSchedule.isPending}
                className="mm-btn mm-btn-primary"
              >
                {updateSchedule.isPending ? "Moving…" : "Move time"}
              </button>
            </div>
          </div>
        </div>
      )}
    </fieldset>
  );
}
