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
    <div className="flex flex-col items-end gap-1.5">
      <p className="text-sm font-medium text-foreground">
        max {total} at a time
        <span className="ml-2 font-normal text-muted-foreground">
          · {used}/{total} active
        </span>
      </p>

      {payload.active_sub_doses.length > 0 && (
        <ul className="text-right text-xs text-muted-foreground">
          {payload.active_sub_doses.map((d) => (
            <li key={d.taken_at}>
              Dose {formatTime(d.taken_at)} — frees {formatTime(d.expires_at)}
            </li>
          ))}
        </ul>
      )}

      {isFull && nextAvailableAt && (
        <p
          role="status"
          className="text-xs font-medium text-warning-foreground"
        >
          Max {total} at a time — next dose at {formatTime(nextAvailableAt)}
        </p>
      )}

      {take.error instanceof WindowFullError && (
        <p role="alert" className="text-xs text-destructive">
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
            ? "mm-btn mm-btn-touch border border-border bg-muted text-muted-foreground"
            : "mm-btn mm-btn-primary mm-btn-touch"
        }
      >
        {isFull ? "Max reached" : "Dose available"}
      </button>
    </div>
  );
}
