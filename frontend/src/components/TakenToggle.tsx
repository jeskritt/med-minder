import { useState } from "react";
import { MinIntervalError, useTakeDose } from "@/hooks/useTakeDose";
import { useUntakeDose } from "@/hooks/useUntakeDose";
import { UntakeConfirmModal } from "@/components/UntakeConfirmModal";
import { formatRemaining } from "@/lib/timers";
import type { TodayItem } from "@/hooks/useToday";

export interface TakenToggleProps {
  scheduleId: string;
  medicationId: string;
  dose: TodayItem["dose"];
  timezone?: string;
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
}: TakenToggleProps) {
  const take = useTakeDose();
  const untake = useUntakeDose();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const isPending = take.isPending || untake.isPending;
  const isTaken = dose !== null;

  const handleClick = () => {
    if (isPending) return;
    if (isTaken) {
      setConfirmOpen(true);
      return;
    }
    take.mutate({ scheduleId, medicationId, timezone });
  };

  const handleConfirm = () => {
    setConfirmOpen(false);
    if (dose) {
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

  return (
    <>
      <button
        type="button"
        onClick={handleClick}
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
    </>
  );
}
