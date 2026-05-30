const FR_005_TEXT =
  "This med has already been taken. Remove the 'taken' status?";

export interface UntakeConfirmModalProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * FR-005 confirmation modal. The body text is fixed and asserted by
 * `UntakeConfirmModal.test.tsx`.
 *
 * Plain conditional render (no native `<dialog>`) so this works in
 * jsdom without polyfills.
 */
export function UntakeConfirmModal({
  open,
  onConfirm,
  onCancel,
}: UntakeConfirmModalProps) {
  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Confirm un-take"
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4 backdrop-blur-sm"
    >
      <div className="mm-card w-full max-w-sm p-6 shadow-xl">
        <p className="mb-4 text-foreground">{FR_005_TEXT}</p>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="mm-btn mm-btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="mm-btn mm-btn-danger"
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}
