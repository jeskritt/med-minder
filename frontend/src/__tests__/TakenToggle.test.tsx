import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api", () => ({
  client: {
    POST: vi.fn(),
    GET: vi.fn(),
  },
  setApiContext: vi.fn(),
  fetchHealthz: vi.fn(),
}));

import { client } from "@/lib/api";
import { TakenToggle } from "@/components/TakenToggle";
import { todayQueryKey, type TodayResponse } from "@/hooks/useToday";

const mockPost = vi.mocked(client.POST);

const SCHEDULE_ID = "11111111-1111-1111-1111-111111111111";
const MED_ID = "22222222-2222-2222-2222-222222222222";

function seedToday(client: QueryClient): TodayResponse {
  const seed: TodayResponse = {
    date: "2026-05-08",
    timezone: "UTC",
    items: [
      {
        schedule_id: SCHEDULE_ID,
        medication_id: MED_ID,
        name: "Lisinopril",
        scheduled_time: "08:00:00",
        quantity_per_dose: "10.000",
        unit: "mg",
        dose: null,
      },
    ],
  };
  client.setQueryData(todayQueryKey(), seed);
  return seed;
}

function renderToggle(
  { withDose }: { withDose: boolean } = { withDose: false },
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const seed = seedToday(queryClient);
  if (withDose) {
    seed.items[0].dose = {
      id: "dose-id-1",
      taken_at: "2026-05-08T15:00:00Z",
    };
    queryClient.setQueryData(todayQueryKey(), seed);
  }
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <TakenToggle
        scheduleId={SCHEDULE_ID}
        medicationId={MED_ID}
        dose={withDose ? seed.items[0].dose : null}
      />
    </QueryClientProvider>,
  );
  return { user: userEvent.setup(), queryClient, ...utils };
}

describe("TakenToggle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders Mark taken when no dose is set", () => {
    renderToggle();
    expect(
      screen.getByRole("button", { name: /mark taken/i }),
    ).toBeInTheDocument();
  });

  it("optimistically writes a dose into the today cache on click", async () => {
    let resolvePost: ((value: unknown) => void) | undefined;
    mockPost.mockImplementation(
      () =>
        new Promise((res) => {
          resolvePost = res;
        }),
    );

    const { user, queryClient } = renderToggle();
    await user.click(screen.getByRole("button", { name: /mark taken/i }));

    // Optimistic write fires synchronously inside onMutate.
    await waitFor(() => {
      const data = queryClient.getQueryData<TodayResponse>(todayQueryKey());
      expect(data?.items[0].dose).not.toBeNull();
    });

    // Settle the request so the mutation can finish cleanly.
    resolvePost?.({ data: undefined, error: undefined });
  });

  it("rolls back and stays untaken on server error", async () => {
    mockPost.mockResolvedValue({
      data: undefined,
      error: { detail: "boom" },
    } as never);

    const { user, queryClient } = renderToggle();
    await user.click(screen.getByRole("button", { name: /mark taken/i }));

    await waitFor(() => {
      const data = queryClient.getQueryData<TodayResponse>(todayQueryKey());
      expect(data?.items[0].dose).toBeNull();
    });
  });

  it("opens the confirm modal when clicked while taken, and POSTs void on confirm", async () => {
    mockPost.mockResolvedValue({
      data: undefined,
      error: undefined,
    } as never);

    const { user } = renderToggle({ withDose: true });
    await user.click(screen.getByRole("button", { name: /taken/i }));

    // FR-005 modal text appears.
    await screen.findByText(
      "This med has already been taken. Remove the 'taken' status?",
    );

    await user.click(screen.getByRole("button", { name: /^confirm$/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalled();
    });
    const [path] = mockPost.mock.calls[0];
    expect(path).toBe("/api/doses/{dose_id}/void");
  });

  it("disables the button while a take mutation is pending", async () => {
    let resolvePost: ((value: unknown) => void) | undefined;
    mockPost.mockImplementation(
      () =>
        new Promise((res) => {
          resolvePost = res;
        }),
    );

    const { user } = renderToggle();
    const button = screen.getByRole("button", { name: /mark taken/i });
    await user.click(button);

    await waitFor(() => {
      expect(button).toBeDisabled();
    });

    // Rapid second click is a no-op: only one POST fired.
    await user.click(button);
    expect(mockPost).toHaveBeenCalledTimes(1);

    resolvePost?.({ data: undefined, error: undefined });
  });
});
