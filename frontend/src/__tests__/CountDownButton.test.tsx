import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/api", () => ({
  client: {
    POST: vi.fn(),
    GET: vi.fn(),
  },
  setApiContext: vi.fn(),
  fetchHealthz: vi.fn(),
}));

import { client } from "@/lib/api";
import { CountDownButton } from "@/components/timers/CountDownButton";
import type { components } from "@/api/v1";

type TimerStateOut = components["schemas"]["TimerStateOut"];

const mockPost = vi.mocked(client.POST);

function countDownState(
  remainingSeconds: number,
  asOf: string = new Date().toISOString(),
): TimerStateOut {
  return {
    mode: "count_down",
    as_of: asOf,
    last_dose_at:
      remainingSeconds > 0
        ? new Date(
            Date.parse(asOf) - (3600 - remainingSeconds) * 1000,
          ).toISOString()
        : null,
    count_down: {
      min_interval_seconds: 3600,
      next_allowed_at:
        remainingSeconds > 0
          ? new Date(Date.parse(asOf) + remainingSeconds * 1000).toISOString()
          : null,
      remaining_seconds: remainingSeconds,
    },
  };
}

function withQueryClient(children: ReactNode): ReactNode {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

afterEach(() => {
  vi.useRealTimers();
  mockPost.mockReset();
});

describe("CountDownButton", () => {
  it("renders the remaining time and disables the button while cooling down", () => {
    render(
      withQueryClient(
        <CountDownButton
          state={countDownState(3000)}
          medicationId="m1"
          scheduleId="s1"
        />,
      ),
    );
    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("50m");
  });

  it("enables the button and shows 'Mark taken' at zero", async () => {
    const user = userEvent.setup();
    mockPost.mockResolvedValueOnce({
      data: { id: "d1" },
      error: undefined,
      response: { status: 201 } as Response,
    });
    render(
      withQueryClient(
        <CountDownButton
          state={countDownState(0)}
          medicationId="m1"
          scheduleId="s1"
        />,
      ),
    );
    const button = screen.getByRole("button", { name: /mark taken/i });
    expect(button).toBeEnabled();

    await user.click(button);
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/doses");
  });

  it("surfaces the MinIntervalViolation body inline on a 409", async () => {
    const user = userEvent.setup();
    const violation = {
      code: "min_interval_not_elapsed" as const,
      medication_id: "m1",
      next_allowed_at: new Date(Date.now() + 50 * 60 * 1000).toISOString(),
      remaining_seconds: 3000,
    };
    mockPost.mockResolvedValueOnce({
      data: undefined,
      error: violation,
      response: { status: 409 } as Response,
    });
    render(
      withQueryClient(
        <CountDownButton
          state={countDownState(0)}
          medicationId="m1"
          scheduleId="s1"
        />,
      ),
    );
    const button = screen.getByRole("button", { name: /mark taken/i });
    await user.click(button);
    expect(await screen.findByRole("alert")).toHaveTextContent("50m");
  });

  it("re-renders at least once per second under fake timers", () => {
    vi.useFakeTimers();
    const asOf = new Date().toISOString();
    render(
      withQueryClient(
        <CountDownButton
          state={countDownState(125, asOf)}
          medicationId="m1"
          scheduleId="s1"
        />,
      ),
    );
    expect(screen.getByRole("button")).toHaveTextContent("2m");
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByRole("button")).toHaveTextContent("1m");
  });
});
