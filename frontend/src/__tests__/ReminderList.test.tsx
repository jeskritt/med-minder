import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api", () => ({ client: { GET: vi.fn() } }));

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

function reminder(overrides: Record<string, unknown>) {
  return {
    id: "r1",
    type: "dose",
    status: "pending",
    scheduled_for: new Date().toISOString(),
    title: "Morning (08:00): Aspirin",
    schedule_id: "s1",
    medication_id: null,
    overdue: false,
    ...overrides,
  };
}

describe("ReminderList", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders reminder titles", async () => {
    mockGet.mockResolvedValue({
      data: { items: [reminder({})] },
      error: undefined,
    } as never);
    renderList();
    expect(await screen.findByText(/Aspirin/)).toBeInTheDocument();
  });

  it("flags overdue reminders", async () => {
    mockGet.mockResolvedValue({
      data: {
        items: [reminder({ id: "r2", title: "Evening: Vitamin D", overdue: true })],
      },
      error: undefined,
    } as never);
    renderList();
    expect(await screen.findByText(/overdue/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no reminders", async () => {
    mockGet.mockResolvedValue({
      data: { items: [] },
      error: undefined,
    } as never);
    renderList();
    expect(await screen.findByText(/no reminders/i)).toBeInTheDocument();
  });
});
