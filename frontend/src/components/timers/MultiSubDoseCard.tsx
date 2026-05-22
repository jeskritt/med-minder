import { useTakeDose, WindowFullError } from "@/hooks/useTakeDose";
import { windowProgress } from "@/lib/timers";
import type { components } from "@/api/v1";

type TimerStateOut = components["schemas"]["TimerStateOut"];

export interface MultiSubDoseCardProps {
  state: TimerStateOut;
  medicationId: string;
  /** Optional — present in the today view, absent in the list/detail. */
  scheduleId?: string;
  timezone?: string;
  /** See `TakenToggle.onBeforeTake` — same contract. */
  onBeforeTake?: () => Promise<boolean>;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function MultiSubDoseCard({
  state,
  medicationId,
  scheduleId,
  timezone,
  onBeforeTake,
}: MultiSubDoseCardProps) {
  const take = useTakeDose();
  const payload = state.multi_sub_dose;

  if (!payload) return null;

  const { used, total, remaining, nextAvailableAt } = windowProgress(state);
  const isFull = remaining === 0;

  const handleClick = async () => {
    if (isFull || take.isPending) return;
    if (onBeforeTake && !(await onBeforeTake())) return;
    take.mutate({ medicationId, scheduleId, timezone });
  };

  return (
    <div className="space-y-1">
      <p className="text-sm text-gray-700">
        max {total} at a time
        <span className="ml-2 text-gray-500">
          · {used}/{total} active
        </span>
      </p>

      {payload.active_sub_doses.length > 0 && (
        <ul className="text-xs text-gray-500">
          {payload.active_sub_doses.map((d) => (
            <li key={d.taken_at}>
              Dose {formatTime(d.taken_at)} — frees {formatTime(d.expires_at)}
            </li>
          ))}
        </ul>
      )}

      {isFull && nextAvailableAt && (
        <p role="status" className="text-xs text-amber-700">
          Max {total} at a time — next dose at {formatTime(nextAvailableAt)}
        </p>
      )}

      {take.error instanceof WindowFullError && (
        <p role="alert" className="mt-1 text-xs text-red-600">
          Max {take.error.body.slots_total} at a time — next dose at{" "}
          {formatTime(take.error.body.next_available_at)}
        </p>
      )}

      <button
        type="button"
        data-testid="dose-control"
        onClick={() => {
          void handleClick();
        }}
        disabled={isFull || take.isPending}
        className={
          isFull
            ? "rounded border border-gray-300 bg-gray-100 px-3 py-1.5 text-sm text-gray-500 disabled:opacity-50"
            : "rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        }
      >
        {isFull ? "Max reached" : "Dose available"}
      </button>
    </div>
  );
}
