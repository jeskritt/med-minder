import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api", () => ({
  client: {
    GET: vi.fn(),
    PUT: vi.fn(),
  },
  setApiContext: vi.fn(),
  fetchHealthz: vi.fn(),
}));

import { client } from "@/lib/api";
import { QuietHoursSection } from "@/components/reminders/QuietHoursSection";

const mockGet = vi.mocked(client.GET);
const mockPut = vi.mocked(client.PUT);

/** A `GET /me` response with overridable quiet-hours fields. */
function meResponse(extra: Record<string, unknown> = {}) {
  return {
    data: {
      id: "u1",
      name: "Molly",
      role: "user",
      timezone: "America/Toronto",
      quiet_hours_start: null,
      quiet_hours_end: null,
      ...extra,
    },
    response: new Response(null, { status: 200 }),
    error: undefined,
  } as never;
}

function renderSection() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    user: userEvent.setup(),
    ...render(
      <QueryClientProvider client={queryClient}>
        <QuietHoursSection />
      </QueryClientProvider>,
    ),
  };
}

describe("QuietHoursSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue(meResponse());
    mockPut.mockResolvedValue(
      meResponse({
        quiet_hours_start: "22:00:00",
        quiet_hours_end: "07:00:00",
      }),
    );
  });

  it("labels with the timezone and hides the inputs until enabled", async () => {
    renderSection();
    expect(
      await screen.findByText(/quiet hours \(america\/toronto\)/i),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Start")).not.toBeInTheDocument();

    const checkbox = screen.getByRole("checkbox", { name: /mute reminders/i });
    await userEvent.setup().click(checkbox);
    expect(await screen.findByLabelText("Start")).toBeInTheDocument();
    expect(screen.getByLabelText("End")).toBeInTheDocument();
  });

  it("saves the window via PUT /me/quiet-hours when enabled", async () => {
    const { user } = renderSection();
    const checkbox = await screen.findByRole("checkbox", {
      name: /mute reminders/i,
    });
    await user.click(checkbox);
    await user.click(screen.getByRole("button", { name: /save quiet hours/i }));

    await waitFor(() => {
      expect(mockPut).toHaveBeenCalledWith("/me/quiet-hours", {
        body: { start: "22:00", end: "07:00" },
      });
    });
  });

  it("clears the window (nulls) when unchecked and saved", async () => {
    mockGet.mockResolvedValue(
      meResponse({
        quiet_hours_start: "22:00:00",
        quiet_hours_end: "07:00:00",
      }),
    );
    const { user } = renderSection();

    // Prefilled "on" state: inputs visible, checkbox checked.
    const checkbox = await screen.findByRole("checkbox", {
      name: /mute reminders/i,
    });
    await waitFor(() => expect(checkbox).toBeChecked());

    await user.click(checkbox); // turn off
    await user.click(screen.getByRole("button", { name: /save quiet hours/i }));

    await waitFor(() => {
      expect(mockPut).toHaveBeenCalledWith("/me/quiet-hours", {
        body: { start: null, end: null },
      });
    });
  });

  it("blocks equal start/end client-side and does not call the API", async () => {
    const { user } = renderSection();
    const checkbox = await screen.findByRole("checkbox", {
      name: /mute reminders/i,
    });
    await user.click(checkbox);

    const end = await screen.findByLabelText("End");
    fireEvent.change(end, { target: { value: "22:00" } }); // == start default

    await user.click(screen.getByRole("button", { name: /save quiet hours/i }));

    expect(
      await screen.findByText(/start and end must be different/i),
    ).toBeInTheDocument();
    expect(mockPut).not.toHaveBeenCalled();
  });
});
