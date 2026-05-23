import { useState } from "react";
import {
  InteractionConflictError,
  MinIntervalError,
  useTakeDose,
} from "@/hooks/useTakeDose";
import { useUntakeDose } from "@/hooks/useUntakeDose";
import { UntakeConfirmModal } from "@/components/UntakeConfirmModal";
import { InteractionConfirmModal } from "@/components/InteractionConfirmModal";
import { formatRemaining } from "@/lib/timers";
import type { TodayItem } from "@/hooks/useToday";

export interface TakenToggleProps {
  /**
   * Optional — absent for unscheduled (PRN) timer rows on /today,
   * which have no schedule slot. Present for normal scheduled slots.
   */
  scheduleId?: string;
  medicationId: string;
  dose: TodayItem["dose"];
  timezone?: string;
  /**
   * Optional async gate that runs before the take mutation. Resolve
   * to `true` to proceed, `false` to short-circuit silently. The
   * /today view uses this for the out-of-schedule confirm modal.
   */
  onBeforeTake?: () => Promise<boolean>;
}

/**
 * Per-slot Taken toggle.
 *
 * - When `dose` is `null`: clicking POSTs `/api/doses` (optimistic).
 * - When `dose` is set: clicking opens the FR-005 modal; confirm POSTs
 *   `/api/doses/{id}/void` (optimistic).
 *
 * The button is `disabled` while either mutation is pending, so a
 * rapid double-click cannot fire a second `POST /api/doses` (per spec
 * §Edge Cases).
 */
export function TakenToggle({
  scheduleId,
  medicationId,
  dose,
  timezone,
  onBeforeTake,
}: TakenToggleProps) {
  const take = useTakeDose();
  const untake = useUntakeDose();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const isPending = take.isPending || untake.isPending;
  const isTaken = dose !== null;

  const handleClick = async () => {
    if (isPending) return;
    if (isTaken) {
      setConfirmOpen(true);
      return;
    }
    if (onBeforeTake && !(await onBeforeTake())) return;
    take.mutate({ scheduleId, medicationId, timezone });
  };

  const handleConfirm = () => {
    setConfirmOpen(false);
    // Untake is only reachable for a taken scheduled slot; PRN rows
    // have `dose === null`, so `scheduleId` is always present here.
    if (dose && scheduleId) {
      untake.mutate({
        doseId: dose.id,
        scheduleId,
        medicationId,
        timezone,
      });
    }
  };

  const handleCancel = () => setConfirmOpen(false);

  const minIntervalError =
    take.error instanceof MinIntervalError ? take.error.body : null;

  const interactionConflict =
    take.error instanceof InteractionConflictError ? take.error.body : null;

  const handleInteractionConfirm = () => {
    take.mutate({
      scheduleId,
      medicationId,
      timezone,
      interactionAcknowledged: true,
    });
  };

  const handleInteractionCancel = () => take.reset();

  return (
    <>
      <button
        type="button"
        data-testid="dose-control"
        onClick={() => {
          void handleClick();
        }}
        disabled={isPending}
        aria-pressed={isTaken}
        className={
          isTaken
            ? "rounded border border-gray-300 bg-gray-100 px-3 py-1.5 text-sm text-gray-500 disabled:opacity-50"
            : "rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        }
      >
        {isTaken ? "Taken" : "Mark taken"}
      </button>
      {minIntervalError && (
        <p role="alert" className="mt-1 text-xs text-red-600">
          Next dose in {formatRemaining(minIntervalError.remaining_seconds)}
        </p>
      )}
      <UntakeConfirmModal
        open={confirmOpen}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
      <InteractionConfirmModal
        open={interactionConflict !== null}
        conflict={interactionConflict}
        onConfirm={handleInteractionConfirm}
        onCancel={handleInteractionCancel}
      />
    </>
  );
}
