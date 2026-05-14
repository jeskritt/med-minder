import type { components } from "@/api/v1";

type TimerStateOut = components["schemas"]["TimerStateOut"];

export function tickFrom(
  state: TimerStateOut,
  monotonicMs: number,
): TimerStateOut {
  if (state.mode !== "count_up") return state;
  const elapsed = state.count_up?.elapsed_seconds;
  if (elapsed == null) return state;
  const asOfMs = Date.parse(state.as_of);
  const deltaSec = Math.max(0, Math.floor((monotonicMs - asOfMs) / 1000));
  return {
    ...state,
    count_up: { elapsed_seconds: elapsed + deltaSec },
  };
}

export function formatElapsed(seconds: number | null): string {
  if (seconds == null) return "no doses recorded yet";
  if (seconds > 86_400) return "over 24h ago";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m ago`;
}

export function formatRemaining(seconds: number): string {
  void seconds;
  return "";
}

export function windowProgress(state: TimerStateOut): {
  used: number;
  total: number;
  expiredUnused: number;
} {
  void state;
  return { used: 0, total: 0, expiredUnused: 0 };
}
