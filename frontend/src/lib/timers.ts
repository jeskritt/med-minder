import type { components } from "@/api/v1";

type TimerStateOut = components["schemas"]["TimerStateOut"];

export function tickFrom(
  state: TimerStateOut,
  monotonicMs: number,
): TimerStateOut {
  void monotonicMs;
  return state;
}

export function formatElapsed(seconds: number, locale?: string): string {
  void seconds;
  void locale;
  return "";
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
