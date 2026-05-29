import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api", () => ({ client: { GET: vi.fn(), POST: vi.fn() } }));

import { client } from "@/lib/api";
import { ReminderList } from "@/components/reminders/ReminderList";

const mockGet = vi.mocked(client.GET);

function renderList() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ReminderList />
    </QueryClientProvider>,
  );
}

/**
 * FR-007: when offline, a data view shows a clear offline/error state and never
 * stale medical data. Because no `/api` response is ever cached (FR-006), an
 * offline fetch simply fails and the view falls back to its error state — there
 * is no cached data to show.
 */
describe("data view when offline (FR-007)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows an error state and no stale rows when the query fails offline", async () => {
    mockGet.mockRejectedValue(new Error("Failed to fetch"));
    renderList();
    expect(
      await screen.findByText(/could not load reminders/i),
    ).toBeInTheDocument();
    // No stale/cached reminder rows are rendered.
    expect(screen.queryByTestId("reminder-list")).not.toBeInTheDocument();
  });
});
