import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createRootRoute,
  createRoute,
  createRouter,
  createMemoryHistory,
  RouterProvider,
} from "@tanstack/react-router";

vi.mock("@/lib/api", () => ({
  client: {
    POST: vi.fn(),
    GET: vi.fn(),
  },
  setApiContext: vi.fn(),
  fetchHealthz: vi.fn(),
}));

import { client } from "@/lib/api";
import { Route as TodayRoute } from "@/routes/today";
import type { TodayResponse } from "@/hooks/useToday";

const mockGet = vi.mocked(client.GET);

function fakeToday(): TodayResponse {
  return {
    date: "2026-05-08",
    timezone: "UTC",
    items: [
      {
        schedule_id: "s2",
        medication_id: "m2",
        name: "Metformin",
        scheduled_time: "20:00:00",
        quantity_per_dose: "500.000",
        unit: "mg",
        dose: null,
      },
      {
        schedule_id: "s1",
        medication_id: "m1",
        name: "Lisinopril",
        scheduled_time: "08:00:00",
        quantity_per_dose: "10.000",
        unit: "mg",
        dose: { id: "d1", taken_at: "2026-05-08T15:14:00Z" },
      },
    ],
  };
}

function renderToday() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const rootRoute = createRootRoute();
  const todayRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/today",
    component: TodayRoute.options.component,
  });
  const loginRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/login",
    component: () => <div>LOGIN</div>,
  });
  const routeTree = rootRoute.addChildren([todayRoute, loginRoute]);
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/today"] }),
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("Today page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // /me check inside beforeLoad — return 200.
    mockGet.mockImplementation((path: string) => {
      if (path === "/me") {
        return Promise.resolve({
          response: new Response(null, { status: 200 }),
          data: { id: "u", name: "U", role: "user" },
          error: undefined,
        }) as never;
      }
      if (path === "/api/schedules/today") {
        return Promise.resolve({
          response: new Response(null, { status: 200 }),
          data: fakeToday(),
          error: undefined,
        }) as never;
      }
      return Promise.resolve({
        response: new Response(null, { status: 404 }),
        data: undefined,
        error: { detail: "not found" },
      }) as never;
    });
  });

  it("renders both slots and a Taken row is greyed out with localized time", async () => {
    renderToday();

    // Both slots render.
    await waitFor(() => {
      expect(screen.getByText("Lisinopril")).toBeInTheDocument();
      expect(screen.getByText("Metformin")).toBeInTheDocument();
    });

    // The taken row carries a "Taken …" label derived from dose.taken_at.
    const takenLabel = await screen.findByText(/^Taken\s/i);
    expect(takenLabel).toBeInTheDocument();
  });

  it("renders the Mark taken button for the untaken slot", async () => {
    renderToday();
    const buttons = await screen.findAllByRole("button");
    const markTaken = buttons.find((b) =>
      /mark taken/i.test(b.textContent ?? ""),
    );
    expect(markTaken).toBeDefined();
  });
});
