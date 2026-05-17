import { render, screen } from "@testing-library/react";
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
import { MultiSubDoseCard } from "@/components/timers/MultiSubDoseCard";
import type { components } from "@/api/v1";

type TimerStateOut = components["schemas"]["TimerStateOut"];

const mockPost = vi.mocked(client.POST);

function withQueryClient(children: ReactNode): ReactNode {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function inactiveNoBanner(): TimerStateOut {
  return {
    mode: "multi_sub_dose",
    as_of: new Date().toISOString(),
    last_dose_at: null,
    multi_sub_dose: {
      window_duration_seconds: 21600,
      slots_total: 3,
      active_window: null,
      previous_window_unused_slots: 0,
    },
  };
}

function activeWindow(used: number): TimerStateOut {
  const now = Date.now();
  return {
    mode: "multi_sub_dose",
    as_of: new Date(now).toISOString(),
    last_dose_at: new Date(now - 3600_000).toISOString(),
    multi_sub_dose: {
      window_duration_seconds: 21600,
      slots_total: 3,
      active_window: {
        window_start: new Date(now - 3600_000).toISOString(),
        window_end: new Date(now + 18000_000).toISOString(),
        doses_in_window: Array.from({ length: used }, (_, i) =>
          new Date(now - 3600_000 + i * 600_000).toISOString(),
        ),
        slots_used: used,
        slots_remaining: 3 - used,
      },
      previous_window_unused_slots: 0,
    },
  };
}

function expiredWithUnused(unused: number): TimerStateOut {
  return {
    mode: "multi_sub_dose",
    as_of: new Date().toISOString(),
    last_dose_at: new Date(Date.now() - 8 * 3600_000).toISOString(),
    multi_sub_dose: {
      window_duration_seconds: 21600,
      slots_total: 3,
      active_window: null,
      previous_window_unused_slots: unused,
    },
  };
}

afterEach(() => {
  mockPost.mockReset();
});

describe("MultiSubDoseCard", () => {
  it("shows an enabled 'Dose available' CTA when no window is active", () => {
    render(
      withQueryClient(
        <MultiSubDoseCard state={inactiveNoBanner()} medicationId="m1" />,
      ),
    );
    const cta = screen.getByRole("button", { name: /dose available/i });
    expect(cta).toBeEnabled();
  });

  it("shows slot progress and keeps the CTA enabled mid-window", () => {
    render(
      withQueryClient(
        <MultiSubDoseCard state={activeWindow(1)} medicationId="m1" />,
      ),
    );
    expect(screen.getByText(/1 of 3/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /dose available/i }),
    ).toBeEnabled();
  });

  it("disables the control when the active window is full", () => {
    render(
      withQueryClient(
        <MultiSubDoseCard state={activeWindow(3)} medicationId="m1" />,
      ),
    );
    expect(screen.getByText(/3 of 3/i)).toBeInTheDocument();
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("renders the FR-008b passive banner without blocking the CTA", () => {
    render(
      withQueryClient(
        <MultiSubDoseCard state={expiredWithUnused(2)} medicationId="m1" />,
      ),
    );
    expect(
      screen.getByText(
        /last window ended with 2 of 3 slots unused — tap when ready/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /dose available/i }),
    ).toBeEnabled();
  });

  it("fires the take mutation when the CTA is tapped", async () => {
    const user = userEvent.setup();
    mockPost.mockResolvedValueOnce({
      data: { id: "d1" },
      error: undefined,
      response: { status: 201 } as Response,
    });
    render(
      withQueryClient(
        <MultiSubDoseCard state={expiredWithUnused(2)} medicationId="m1" />,
      ),
    );
    await user.click(screen.getByRole("button", { name: /dose available/i }));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/doses");
  });
});
