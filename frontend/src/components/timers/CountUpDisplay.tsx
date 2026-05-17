import { useEffect, useState } from "react";
import { formatElapsed, tickFrom } from "@/lib/timers";
import type { components } from "@/api/v1";

type TimerStateOut = components["schemas"]["TimerStateOut"];

export interface CountUpDisplayProps {
  state: TimerStateOut;
}

export function CountUpDisplay({ state }: CountUpDisplayProps) {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (state.count_up?.elapsed_seconds == null) return;
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [state.as_of, state.count_up?.elapsed_seconds]);

  const ticked = tickFrom(state, nowMs);
  return <span>{formatElapsed(ticked.count_up?.elapsed_seconds ?? null)}</span>;
}
