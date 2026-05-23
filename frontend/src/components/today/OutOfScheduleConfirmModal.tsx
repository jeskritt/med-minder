const OUT_OF_SCHEDULE_TEXT =
  "This is out of schedule — either it's not normally scheduled today, " +
  "or the scheduled time is more than 2 hours from now. Mark it taken anyway?";

export interface OutOfScheduleConfirmModalProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Confirms an off-schedule take (UX-enhancements). Mirrors the
 * `UntakeConfirmModal` / `InteractionConfirmModal` pattern: plain
 * conditional render (no native `<dialog>`) so jsdom works.
 *
 * "Out of schedule" is calculated in the caller; this component is
 * purely presentational so each dose-control can lift its own check.
 */
export function OutOfScheduleConfirmModal({
  open,
  onConfirm,
  onCancel,
}: OutOfScheduleConfirmModalProps) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Confirm out-of-schedule dose"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="rounded-lg border bg-white p-6 shadow">
        <p className="mb-4">{OUT_OF_SCHEDULE_TEXT}</p>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded border px-3 py-1.5 text-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded bg-amber-600 px-3 py-1.5 text-sm text-white"
          >
            Take anyway
          </button>
        </div>
      </div>
    </div>
  );
}
