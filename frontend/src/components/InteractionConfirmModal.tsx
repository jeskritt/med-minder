import type { components } from "@/api/v1";
import { formatRemaining } from "@/lib/timers";

type InteractionCooldownViolation =
  components["schemas"]["InteractionCooldownViolation"];

export interface InteractionConfirmModalProps {
  open: boolean;
  conflict: InteractionCooldownViolation | null;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Phase 6 "take anyway" confirmation (ADR-0008). Mirrors
 * `UntakeConfirmModal` (plain conditional render, no native
 * `<dialog>`, works in jsdom). Unlike a non-overridable Phase 5
 * overdose 409 — which is rendered as an inline dead-end — an
 * interaction conflict is *always overridable*: this modal lets the
 * user explicitly proceed, and the override is audited server-side.
 */
export function InteractionConfirmModal({
  open,
  conflict,
  onConfirm,
  onCancel,
}: InteractionConfirmModalProps) {
  if (!open || conflict === null) return null;

  const names = conflict.conflicts
    .map((c) => c.conflicting_medication_name)
    .join(", ");
  const remaining = formatRemaining(conflict.remaining_seconds);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Confirm interaction override"
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4 backdrop-blur-sm"
    >
      <div className="mm-card w-full max-w-sm p-6 shadow-xl">
        <p className="mb-2 font-semibold text-foreground">
          Interacts with {names}
        </p>
        <p className="mb-4 text-sm text-muted-foreground">
          Safe in {remaining}. You can take it anyway — this will be recorded.
        </p>
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
            Take anyway
          </button>
        </div>
      </div>
    </div>
  );
}
