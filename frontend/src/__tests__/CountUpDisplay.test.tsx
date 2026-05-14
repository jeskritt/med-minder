import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { CountUpDisplay } from "@/components/timers/CountUpDisplay";
import type { components } from "@/api/v1";

type TimerStateOut = components["schemas"]["TimerStateOut"];

function countUpState(
  elapsedSeconds: number | null,
  asOf: string = new Date().toISOString(),
  lastDoseAt: string | null = elapsedSeconds === null
    ? null
    : new Date(Date.parse(asOf) - elapsedSeconds * 1000).toISOString(),
): TimerStateOut {
  return {
    mode: "count_up",
    as_of: asOf,
    last_dose_at: lastDoseAt,
    count_up: { elapsed_seconds: elapsedSeconds },
  };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("CountUpDisplay", () => {
  it("renders 'no doses recorded yet' when elapsed_seconds is null", () => {
    render(<CountUpDisplay state={countUpState(null)} />);
    expect(screen.getByText("no doses recorded yet")).toBeTruthy();
  });

  it("renders 'over 24h ago' when elapsed_seconds exceeds a day", () => {
    render(<CountUpDisplay state={countUpState(90_000)} />);
    expect(screen.getByText("over 24h ago")).toBeTruthy();
  });

  it("re-renders at least once per minute under fake timers", () => {
    vi.useFakeTimers();
    const asOf = new Date().toISOString();
    render(<CountUpDisplay state={countUpState(180, asOf)} />);
    expect(screen.getByText("3m ago")).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByText("4m ago")).toBeTruthy();
  });
});
