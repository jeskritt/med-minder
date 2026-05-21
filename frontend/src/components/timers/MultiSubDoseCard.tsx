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

  const { used, total, expiredUnused } = windowProgress(state);
  const win = payload.active_window;
  const isFull = win !== null && win.slots_remaining === 0;

  const handleClick = async () => {
    if (isFull || take.isPending) return;
    if (onBeforeTake && !(await onBeforeTake())) return;
    take.mutate({ medicationId, scheduleId, timezone });
  };

  return (
    <div className="space-y-1">
      <p className="text-sm text-gray-700">
        {used} of {total} this window
        {win && (
          <span className="ml-2 text-gray-500">
            · window ends {formatTime(win.window_end)}
          </span>
        )}
      </p>

      {win && win.doses_in_window.length > 0 && (
        <ul className="text-xs text-gray-500">
          {win.doses_in_window.map((d, i) => (
            <li key={`${d}-${i}`}>
              Sub-dose {i + 1}: {formatTime(d)}
            </li>
          ))}
        </ul>
      )}

      {expiredUnused > 0 && (
        <p role="status" className="text-xs text-amber-700">
          Last window ended with {expiredUnused} of {total} slots unused — tap
          when ready
        </p>
      )}

      {take.error instanceof WindowFullError && (
        <p role="alert" className="mt-1 text-xs text-red-600">
          Window full — {take.error.body.slots_used} of{" "}
          {take.error.body.slots_total} this window
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
        {isFull ? "Window full" : "Dose available"}
      </button>
    </div>
  );
}
