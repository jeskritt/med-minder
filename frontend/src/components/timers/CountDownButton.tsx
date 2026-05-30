import { useEffect, useRef, useState } from "react";
import { Clock } from "lucide-react";
import { MinIntervalError, useTakeDose } from "@/hooks/useTakeDose";
import { formatRemaining } from "@/lib/timers";
import type { components } from "@/api/v1";

type TimerStateOut = components["schemas"]["TimerStateOut"];

export interface CountDownButtonProps {
  state: TimerStateOut;
  medicationId: string;
  /** Optional — present in the today view, absent in the medications list. */
  scheduleId?: string;
  timezone?: string;
  /** See `TakenToggle.onBeforeTake` — same contract. */
  onBeforeTake?: () => Promise<boolean>;
}

function tickedRemaining(state: TimerStateOut, nowMs: number): number {
  const seed = state.count_down?.remaining_seconds ?? 0;
  const asOfMs = Date.parse(state.as_of);
  const deltaSec = Math.max(0, Math.floor((nowMs - asOfMs) / 1000));
  return Math.max(0, seed - deltaSec);
}

export function CountDownButton({
  state,
  medicationId,
  scheduleId,
  timezone,
  onBeforeTake,
}: CountDownButtonProps) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  const take = useTakeDose();
  const wasZeroRef = useRef<boolean>(
    (state.count_down?.remaining_seconds ?? 0) <= 0,
  );

  useEffect(() => {
    if ((state.count_down?.remaining_seconds ?? 0) <= 0) return;
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [state.as_of, state.count_down?.remaining_seconds]);

  const remaining = tickedRemaining(state, nowMs);
  const isReady = remaining === 0;

  // FR-010: single short vibration on the zero crossing while visible.
  useEffect(() => {
    if (isReady && !wasZeroRef.current) {
      wasZeroRef.current = true;
      if (
        typeof document !== "undefined" &&
        document.visibilityState === "visible" &&
        typeof navigator !== "undefined" &&
        typeof navigator.vibrate === "function"
      ) {
        navigator.vibrate(200);
      }
    }
    if (!isReady) {
      wasZeroRef.current = false;
    }
  }, [isReady]);

  const handleClick = async () => {
    if (!isReady || take.isPending) return;
    if (onBeforeTake && !(await onBeforeTake())) return;
    take.mutate({ medicationId, scheduleId, timezone });
  };

  const minIntervalError =
    take.error instanceof MinIntervalError ? take.error.body : null;

  return (
    <>
      <button
        type="button"
        data-testid="dose-control"
        onClick={() => {
          void handleClick();
        }}
        disabled={!isReady || take.isPending}
        className={
          isReady
            ? "mm-btn mm-btn-primary mm-btn-touch"
            : "mm-btn mm-btn-touch border border-border bg-muted font-mono text-muted-foreground tabular-nums"
        }
      >
        {isReady ? (
          "Mark taken"
        ) : (
          <>
            <Clock className="size-4" />
            {formatRemaining(remaining)}
          </>
        )}
      </button>
      {minIntervalError && (
        <p role="alert" className="mt-1 text-xs text-destructive">
          Next dose in {formatRemaining(minIntervalError.remaining_seconds)}
        </p>
      )}
    </>
  );
}
