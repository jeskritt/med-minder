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
  if (seconds <= 0) return "ready";
  if (seconds < 60) return "<1m";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

export function windowProgress(state: TimerStateOut): {
  used: number;
  total: number;
  remaining: number;
  nextAvailableAt: string | null;
} {
  if (state.mode !== "multi_sub_dose" || !state.multi_sub_dose) {
    return { used: 0, total: 0, remaining: 0, nextAvailableAt: null };
  }
  const payload = state.multi_sub_dose;
  return {
    used: payload.slots_used,
    total: payload.max_concurrent,
    remaining: payload.slots_remaining,
    nextAvailableAt: payload.next_available_at,
  };
}
