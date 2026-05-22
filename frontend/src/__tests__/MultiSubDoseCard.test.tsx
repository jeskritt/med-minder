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

const WINDOW_S = 21600; // 6h
const mockPost = vi.mocked(client.POST);

function withQueryClient(children: ReactNode): ReactNode {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function inactive(): TimerStateOut {
  return {
    mode: "multi_sub_dose",
    as_of: new Date().toISOString(),
    last_dose_at: null,
    multi_sub_dose: {
      window_duration_seconds: WINDOW_S,
      max_concurrent: 3,
      active_sub_doses: [],
      slots_used: 0,
      slots_remaining: 3,
      next_available_at: null,
    },
  };
}

/** `used` doses still active, oldest taken 1h ago, 30m apart. */
function active(used: number): TimerStateOut {
  const now = Date.now();
  const subs = Array.from({ length: used }, (_, i) => {
    const takenMs = now - 3600_000 + i * 1800_000;
    return {
      taken_at: new Date(takenMs).toISOString(),
      expires_at: new Date(takenMs + WINDOW_S * 1000).toISOString(),
    };
  });
  const full = used >= 3;
  return {
    mode: "multi_sub_dose",
    as_of: new Date(now).toISOString(),
    last_dose_at: subs.length ? subs[subs.length - 1].taken_at : null,
    multi_sub_dose: {
      window_duration_seconds: WINDOW_S,
      max_concurrent: 3,
      active_sub_doses: subs,
      slots_used: used,
      slots_remaining: Math.max(0, 3 - used),
      next_available_at: full ? subs[0].expires_at : null,
    },
  };
}

afterEach(() => {
  mockPost.mockReset();
});

describe("MultiSubDoseCard", () => {
  it("shows an enabled 'Dose available' CTA when nothing is active", () => {
    render(
      withQueryClient(
        <MultiSubDoseCard state={inactive()} medicationId="m1" />,
      ),
    );
    expect(screen.getByText(/max 3 at a time/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /dose available/i }),
    ).toBeEnabled();
  });

  it("shows active-dose count and keeps the CTA enabled below capacity", () => {
    render(
      withQueryClient(<MultiSubDoseCard state={active(1)} medicationId="m1" />),
    );
    expect(screen.getByText(/1\/3 active/i)).toBeInTheDocument();
    // One per-dose row with its own "frees" time.
    expect(screen.getByText(/frees/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /dose available/i }),
    ).toBeEnabled();
  });

  it("disables the control and shows the next-dose time at capacity", () => {
    render(
      withQueryClient(<MultiSubDoseCard state={active(3)} medicationId="m1" />),
    );
    expect(screen.getByText(/3\/3 active/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /max reached/i })).toBeDisabled();
    expect(screen.getByText(/next dose at/i)).toBeInTheDocument();
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
        <MultiSubDoseCard state={inactive()} medicationId="m1" />,
      ),
    );
    await user.click(screen.getByRole("button", { name: /dose available/i }));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/doses");
  });
});
